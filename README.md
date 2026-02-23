# 🧠 Object Detection API Lambda

End-to-end object detection application using a React + Vite frontend and an AWS Lambda backend powered by Amazon Rekognition.

## 📚 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [API Contract](#api-contract)
- [Local Setup (Frontend)](#local-setup-frontend)
- [Deployment Notes](#deployment-notes)
- [Contributor Notes](#contributor-notes)
- [Author](#author)

## 🔍 Overview

This project provides:

- Frontend UI to upload an image and choose detection settings.
- Backend API to process image payloads and return detected object labels.
- Confidence-based results display for each detected label.

## 🏗️ Architecture

The solution follows a client-to-cloud pipeline:

1. **Frontend (React + Vite)** accepts image upload and input parameters.
2. **Amazon API Gateway** receives HTTPS requests from the frontend.
3. **AWS Lambda** validates input, decodes base64 image data, and invokes Rekognition.
4. **Amazon Rekognition** runs `DetectLabels` and returns object labels with confidence scores.

![Object Detection Architecture](Object%20Detection%20Arch.png)

## 🛠️ Tech Stack

- React
- Vite
- AWS Lambda (Python)
- Amazon API Gateway
- Amazon Rekognition

## 📁 Project Structure

```text
.
├── Lambda_handler.py           # Lambda function for validation + Rekognition call
├── ObjectDetectionUI.jsx       # Main object detection UI logic
├── ObjectDetectionUI.css       # Styles for object detection UI
├── src/                        # Vite app source
├── public/                     # Static assets
└── README.md
```

## ⚙️ How It Works

1. User selects an image in the frontend.
2. Frontend converts image data to base64.
3. Frontend posts payload to API Gateway.
4. Lambda decodes payload and calls Rekognition.
5. Lambda returns labels and confidence values.
6. Frontend renders labels and confidence bars.

## 🔌 API Contract

### Request Body

```json
{
  "body": "<base64 image string>",
  "maxLabels": 5,
  "confidence": 100
}
```

- `body`: Required base64-encoded image data.
- `maxLabels`: Optional, default `5`, range `1-100`.
- `confidence`: Optional, default `100`, range `0-100`.

### Response Body

```json
[
  {
    "Label": "Person",
    "Confidence": 99.23
  }
]
```

## 💻 Local Setup (Frontend)

```bash
npm install
npm run dev
```

## 🚀 Deployment Notes

- Backend Lambda must be deployed and connected to API Gateway.
- Frontend `API_ENDPOINT` in `ObjectDetectionUI.jsx` must point to your active API Gateway stage URL.
- Lambda should return CORS headers to allow browser-based calls from the frontend.

## 🤝 Contributor Notes

- Keep request/response field names aligned between frontend and Lambda handler.
- Validate `maxLabels` and `confidence` in both UI and backend for safer input handling.
- If API Gateway URL changes by environment, update frontend configuration accordingly.

## ✍️ Author

- DJ Rajasekar
