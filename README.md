# Object Detection Project

This project is an end-to-end Object Detection solution that combines:

- A React + Vite frontend for uploading images and viewing label detection results.
- An AWS Lambda backend that uses Amazon Rekognition to detect objects in images.

The project association is:

- Frontend UI: image upload, confidence/max-label inputs, result rendering.
- Backend API: receives base64 image data, runs Rekognition DetectLabels, returns label + confidence.

## Project Components

- ObjectDetectionUI.jsx: Main user interface for file upload, API request, and result display.
- ObjectDetectionUI.css: Styles for the object detection interface.
- Lambda_handler.py: AWS Lambda handler for image decoding, parameter validation, and Rekognition calls.

## Project Architecture

This solution follows a simple client-to-cloud request pipeline:

- Presentation Layer (Frontend): React + Vite UI for upload, parameter input, and result rendering.
- API Layer: Amazon API Gateway endpoint that receives HTTPS requests from the browser.
- Compute Layer: AWS Lambda function that validates payload, decodes image, and calls Rekognition.
- AI Service Layer: Amazon Rekognition DetectLabels for object detection.

![Object Detection Architecture](Object%20Detection%20Arch.png)

### Data Contract Between Frontend and Backend

- Request body fields: `body` (base64 image), `maxLabels` (1-100), `confidence` (0-100).
- Response body: JSON array of objects with `Label` and `Confidence`.

### Deployment Association

- Frontend app runs locally with Vite during development.
- Backend Lambda is deployed in AWS and exposed through API Gateway.
- The frontend `API_ENDPOINT` in ObjectDetectionUI.jsx must point to the active API Gateway stage URL.

## Request/Response Flow

1. User selects an image in the frontend.
2. Frontend converts the image to base64 and posts JSON to API Gateway.
3. Lambda receives the request body, decodes the image, and calls Rekognition.
4. Lambda returns detected labels and confidence values.
5. Frontend displays the detections with confidence bars.

## API Payload Contract

Expected request payload sent from frontend:

{
	"body": "<base64 image string>",
	"maxLabels": 15,
	"confidence": 80
}

Typical successful response body:

[
	{
		"Label": "Person",
		"Confidence": 99.23
	}
]

## Run Frontend Locally

- Install dependencies: npm install
- Start dev server: npm run dev

## Notes for New Team Members

- Update the API endpoint in ObjectDetectionUI.jsx if your API Gateway URL differs by environment.
- Lambda expects base64 image content and supports optional maxLabels and confidence values.
- CORS headers are returned by Lambda so the frontend can call the API from browser clients.
