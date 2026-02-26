import json
import boto3
import logging
import base64
from io import BytesIO
from PIL import Image

# AWS Rekognition client is created once per execution environment (reused on warm starts).
rekognition = boto3.client('rekognition')

# Lambda logger setup for CloudWatch visibility.
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _remove_people_from_image(source_image, person_instances):
    # Approximate person removal by replacing each detected person region
    # with stretched nearby background strips.
    #
    # Important notes about this approach:
    # - This is not semantic inpainting; it is a simple fill strategy.
    # - Rekognition returns normalized bounding boxes (0..1), so we convert
    #   each one to absolute pixel coordinates before editing the image.
    # - For each detected person box, we sample a thin strip from the nearest
    #   available side (top, bottom, left, then right), resize it to the full
    #   person box size, and paste it over that box.
    # - Result quality depends on scene complexity; textured or crowded scenes
    #   may show visible artifacts where people were removed.
    working_image = source_image.copy()
    width, height = working_image.size

    for instance in person_instances:
        # Rekognition instance format includes BoundingBox with normalized values:
        # { Left, Top, Width, Height } in range 0..1 relative to image size.
        bbox = instance.get('BoundingBox') or {}
        left = int((bbox.get('Left', 0) or 0) * width)
        top = int((bbox.get('Top', 0) or 0) * height)
        box_width = int((bbox.get('Width', 0) or 0) * width)
        box_height = int((bbox.get('Height', 0) or 0) * height)

        if box_width <= 0 or box_height <= 0:
            continue

        right = min(width, left + box_width)
        bottom = min(height, top + box_height)
        left = max(0, left)
        top = max(0, top)

        if right <= left or bottom <= top:
            continue

        # Define sampling strip thickness:
        # - roughly 25% of the target box dimension
        # - clamped to avoid strips that are too tiny or too large
        strip_height = max(2, min((bottom - top) // 4, 24))
        strip_width = max(2, min((right - left) // 4, 24))

        replacement_patch = None

        # Pick a source strip from nearby background in this preference order:
        # 1) immediately above box
        # 2) immediately below box
        # 3) immediately left of box
        # 4) immediately right of box
        #
        # This order generally preserves vertical scene continuity first.
        if top - strip_height >= 0:
            replacement_patch = working_image.crop((left, top - strip_height, right, top))
        elif bottom + strip_height <= height:
            replacement_patch = working_image.crop((left, bottom, right, bottom + strip_height))
        elif left - strip_width >= 0:
            replacement_patch = working_image.crop((left - strip_width, top, left, bottom))
        elif right + strip_width <= width:
            replacement_patch = working_image.crop((right, top, right + strip_width, bottom))

        # Skip if no valid neighboring pixels are available for replacement.
        if replacement_patch is None or replacement_patch.size[0] == 0 or replacement_patch.size[1] == 0:
            continue

        # Stretch sampled strip to fill entire person bounding box and paste.
        # Bilinear interpolation keeps the transition smoother than nearest-neighbor.
        replacement_patch = replacement_patch.resize((right - left, bottom - top), Image.Resampling.BILINEAR)
        working_image.paste(replacement_patch, (left, top, right, bottom))

    return working_image


def lambda_handler(event, context):
    # Entry point for API Gateway -> Lambda integration.
    # Expected request payload (JSON):
    # {
    #   "body": "<base64 image string>",
    #   "maxLabels": 5,
    #   "confidence": 90,
    #   "removePeople": false
    # }
    # Note: API Gateway may wrap this in event['body'] as a string.
    logger.info("Get the Event")
    try:
        logger.info(f"Full event keys: {event.keys() if isinstance(event, dict) else 'NOT A DICT'}")
        logger.info(f"Full event: {event}")

        data = {}
        base64_string = None

        # Validate event shape first.
        if 'body' not in event:
            logger.error(f"Event structure: {json.dumps(event, default=str)}")
            raise ValueError("No 'body' key found in event")
        
        body = event['body']
        logger.info(f"Raw body type: {type(body)}, length: {len(body) if body else 0}")
        
        # Reject empty payload early.
        if not body or body == '':
            logger.error("Body is empty string")
            raise ValueError("Request body is empty")
        
        # Body can arrive as dict or JSON string depending on gateway/client settings.
        if isinstance(body, dict):
            logger.info("Body is already a dict")
            data = body
        else:
            # Parse serialized JSON body.
            try:
                logger.info(f"Attempting to parse body as JSON...")
                data = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Body content (first 500 chars): {str(body)[:500]}")
                # Fallback: accept raw base64 body if caller sent image data directly.
                if body and not body.startswith('{') and len(body) > 100:
                    logger.info("Body looks like base64, using directly")
                    base64_string = body
                else:
                    raise ValueError(f"Invalid JSON in request body: {str(e)}")
        
        # Extract image data from normalized payload.
        if base64_string is None:
            if isinstance(data, dict):
                base64_string = data.get('body')
            elif isinstance(data, str):
                base64_string = data

        # Support additional common event shapes where parameters/body are top-level.
        if base64_string is None and isinstance(event, dict):
            candidate_body = event.get('image') or event.get('base64') or event.get('base64Image')
            if isinstance(candidate_body, str) and candidate_body:
                base64_string = candidate_body
        
        # Read optional inference parameters (with safe defaults).
        max_labels = 5
        min_confidence = 90
        remove_people = False

        if isinstance(data, dict):
            max_labels = data.get('maxLabels', max_labels)
            min_confidence = data.get('confidence', min_confidence)
            remove_people = data.get('removePeople', remove_people)

        if isinstance(event, dict):
            max_labels = event.get('maxLabels', max_labels)
            min_confidence = event.get('confidence', min_confidence)
            remove_people = event.get('removePeople', remove_people)

            query_params = event.get('queryStringParameters') or {}
            if isinstance(query_params, dict):
                max_labels = query_params.get('maxLabels', max_labels)
                min_confidence = query_params.get('confidence', min_confidence)
                remove_people = query_params.get('removePeople', remove_people)
        
        # Convert to int; if malformed, fall back to defaults.
        try:
            max_labels = int(max_labels)
            min_confidence = int(min_confidence)
        except (ValueError, TypeError):
            logger.warning(f"Invalid parameter types: maxLabels={max_labels}, confidence={min_confidence}")
            max_labels = 5
            min_confidence = 90

        if isinstance(remove_people, str):
            remove_people = remove_people.strip().lower() in ('true', '1', 'yes', 'y', 'on')
        else:
            remove_people = bool(remove_people)
        
        # Enforce Rekognition-compatible ranges.
        max_labels = max(1, min(100, max_labels))
        min_confidence = max(0, min(100, min_confidence))
        
        logger.info(
            f"Detection parameters: MaxLabels={max_labels}, MinConfidence={min_confidence}, RemovePeople={remove_people}"
        )
        
        if not base64_string:
            raise ValueError("No base64 image data found in request body")
        
        logger.info(f"Base64 string length: {len(base64_string)}")

        # Decode incoming image bytes.
        decoded_data = base64.b64decode(base64_string)
        logger.info(f"Decoded image data length: {len(decoded_data)}")

        # Open via Pillow for format normalization before sending to Rekognition.
        image_stream = BytesIO(decoded_data)
        image_stream.seek(0)
        image = Image.open(image_stream)
        logger.info(f"Image opened successfully: {image.format} {image.size} {image.mode}")

        # Convert transparency modes to RGB because output is re-encoded as JPEG.
        if image.mode in ('RGBA', 'LA', 'P'):
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = rgb_image

        stream = BytesIO()
        image.save(stream, format="JPEG")
        image_binary = stream.getvalue()

        # Call Rekognition DetectLabels API.
        logger.info("Detecting the Labels....")

        response = rekognition.detect_labels(
            Image={
                'Bytes': image_binary
            },
            MaxLabels=max_labels,
            MinConfidence=min_confidence
        )

        # Keep response lean for the frontend: only label name + confidence.
        labels_info = [
            {
                'Label': label_info['Name'],
                'Confidence': label_info['Confidence']
            }
            for label_info in response['Labels']
        ]

        # Build explicit person-detection metadata for frontend use.
        person_label = next(
            (label for label in response['Labels'] if label.get('Name', '').lower() == 'person'),
            None
        )
        person_present = person_label is not None
        person_confidence = person_label.get('Confidence') if person_present else None
        person_count = len(person_label.get('Instances', [])) if person_present else 0

        regenerated_image_base64 = None
        if remove_people and person_present:
            # Instances contains one bounding box per detected person instance.
            # Each box is used as a mask target for background patch replacement.
            person_instances = person_label.get('Instances', [])
            regenerated_image = _remove_people_from_image(image, person_instances)
            regenerated_stream = BytesIO()
            regenerated_image.save(regenerated_stream, format="JPEG")
            regenerated_stream.seek(0)
            regenerated_image_base64 = base64.b64encode(regenerated_stream.read()).decode('utf-8')

        result_payload = {
            'labels': labels_info,
            'personPresent': person_present,
            'personConfidence': person_confidence,
            'personCount': person_count,
            'removePeopleRequested': remove_people,
            'peopleRemoved': bool(remove_people and person_present),
            'regeneratedImageBase64': regenerated_image_base64
        }

        # Success response is API Gateway proxy format with CORS headers.
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Content-Type': 'application/json'
            },
            'body': json.dumps(result_payload)
        }
    except Exception as e:
        # Fail safely with details in logs and a generic API error payload.
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Content-Type': 'application/json'
            },
            'body': json.dumps(f"Failed because of: {str(e)}")
        }