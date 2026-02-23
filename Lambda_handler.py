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


def lambda_handler(event, context):
    # Entry point for API Gateway -> Lambda integration.
    # Expected request payload (JSON):
    # {
    #   "body": "<base64 image string>",
    #   "maxLabels": 5,
    #   "confidence": 90
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

        if isinstance(data, dict):
            max_labels = data.get('maxLabels', max_labels)
            min_confidence = data.get('confidence', min_confidence)

        if isinstance(event, dict):
            max_labels = event.get('maxLabels', max_labels)
            min_confidence = event.get('confidence', min_confidence)

            query_params = event.get('queryStringParameters') or {}
            if isinstance(query_params, dict):
                max_labels = query_params.get('maxLabels', max_labels)
                min_confidence = query_params.get('confidence', min_confidence)
        
        # Convert to int; if malformed, fall back to defaults.
        try:
            max_labels = int(max_labels)
            min_confidence = int(min_confidence)
        except (ValueError, TypeError):
            logger.warning(f"Invalid parameter types: maxLabels={max_labels}, confidence={min_confidence}")
            max_labels = 5
            min_confidence = 90
        
        # Enforce Rekognition-compatible ranges.
        max_labels = max(1, min(100, max_labels))
        min_confidence = max(0, min(100, min_confidence))
        
        logger.info(f"Detection parameters: MaxLabels={max_labels}, MinConfidence={min_confidence}")
        
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

        # Success response is API Gateway proxy format with CORS headers.
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Content-Type': 'application/json'
            },
            'body': json.dumps(labels_info)
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