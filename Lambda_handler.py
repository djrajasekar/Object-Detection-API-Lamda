import json
import boto3
import logging
import base64
from io import BytesIO
from PIL import Image

# Initialize AWS Rekognition client
rekognition = boto3.client('rekognition')

# Set the Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    # Get the image from the API Gateway event
    logger.info("Get the Event")
    try:
        logger.info(f"Full event keys: {event.keys() if isinstance(event, dict) else 'NOT A DICT'}")
        logger.info(f"Full event: {event}")

        # Handle different event structures
        if 'body' not in event:
            logger.error(f"Event structure: {json.dumps(event, default=str)}")
            raise ValueError("No 'body' key found in event")
        
        body = event['body']
        logger.info(f"Raw body type: {type(body)}, length: {len(body) if body else 0}")
        
        # Handle empty body
        if not body or body == '':
            logger.error("Body is empty string")
            raise ValueError("Request body is empty")
        
        # Check if body is already a dict (API Gateway with binary mode off)
        if isinstance(body, dict):
            logger.info("Body is already a dict")
            data = body
        else:
            # Body is a string - parse it as JSON
            try:
                logger.info(f"Attempting to parse body as JSON...")
                data = json.loads(body)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Body content (first 500 chars): {str(body)[:500]}")
                # Maybe it's not JSON but raw base64?
                if body and not body.startswith('{') and len(body) > 100:
                    logger.info("Body looks like base64, using directly")
                    base64_string = body
                else:
                    raise ValueError(f"Invalid JSON in request body: {str(e)}")
        
        # Extract base64 image data and parameters
        if 'base64_string' not in locals():
            base64_string = data.get('body') if isinstance(data, dict) else data
        
        # Extract optional parameters with defaults
        max_labels = data.get('maxLabels', 15) if isinstance(data, dict) else 15
        min_confidence = data.get('confidence', 80) if isinstance(data, dict) else 80
        
        # Validate parameters
        try:
            max_labels = int(max_labels)
            min_confidence = int(min_confidence)
        except (ValueError, TypeError):
            logger.warning(f"Invalid parameter types: maxLabels={max_labels}, confidence={min_confidence}")
            max_labels = 15
            min_confidence = 80
        
        # Clamp values to valid ranges
        max_labels = max(1, min(100, max_labels))
        min_confidence = max(0, min(100, min_confidence))
        
        logger.info(f"Detection parameters: MaxLabels={max_labels}, MinConfidence={min_confidence}")
        
        if not base64_string:
            raise ValueError("No base64 image data found in request body")
        
        logger.info(f"Base64 string length: {len(base64_string)}")

        # Decode the Image Binary
        decoded_data = base64.b64decode(base64_string)
        logger.info(f"Decoded image data length: {len(decoded_data)}")

        # Process the Image - reset stream position
        image_stream = BytesIO(decoded_data)
        image_stream.seek(0)
        image = Image.open(image_stream)
        logger.info(f"Image opened successfully: {image.format} {image.size} {image.mode}")

        # Convert RGBA to RGB (JPEG doesn't support transparency)
        if image.mode in ('RGBA', 'LA', 'P'):
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = rgb_image

        stream = BytesIO()
        image.save(stream, format="JPEG")
        image_binary = stream.getvalue()

        # Perform object detection
        logger.info("Detecting the Labels....")

        response = rekognition.detect_labels(
            Image={
                'Bytes': image_binary
            },
            MaxLabels=max_labels,
            MinConfidence=min_confidence
        )

        # Extract only labels and confidence
        labels_info = [
            {
                'Label': label_info['Name'],
                'Confidence': label_info['Confidence']
            }
            for label_info in response['Labels']
        ]

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