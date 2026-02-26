import React, { useState } from 'react';
import './ObjectDetectionUI.css';

const ObjectDetectionUI = () => {
  // Core UI state: selected file, preview image, request lifecycle, and API output.
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [personDetection, setPersonDetection] = useState(null);
  const [error, setError] = useState(null);

  // API tuning values sent to Lambda/Rekognition.
  const [maxLabels, setMaxLabels] = useState(5);
  const [confidence, setConfidence] = useState(90);

  // API Gateway endpoint for the Lambda function.
  // If this changes by environment (dev/test/prod), move to an env variable later.
  const API_ENDPOINT = 'https://t01brchlhi.execute-api.us-east-1.amazonaws.com/dev/detection';

  // Handles file input changes: stores the file and builds a browser preview.
  const handleImageSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setImage(file);
      setError(null);
      setResults(null);
      setPersonDetection(null);

      // Create a base64 preview for immediate user feedback.
      const reader = new FileReader();
      reader.onloadend = () => {
        setPreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  // Submits the selected image to Lambda and normalizes different response shapes.
  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!image) {
      setError('Please select an image');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);
    setPersonDetection(null);

    try {
      // Read file as data URL, then strip the prefix to keep only raw base64.
      const reader = new FileReader();
      reader.onload = async () => {
        const base64String = reader.result.split(',')[1];
        console.log('✅ Base64 string created, length:', base64String.length);
        console.log('📤 Sending request to:', API_ENDPOINT);

        try {
          // Request contract expected by Lambda handler.
          const requestBody = JSON.stringify({
            body: base64String,
            maxLabels: parseInt(maxLabels),
            confidence: parseInt(confidence),
          });
          console.log('📦 Request body size:', requestBody.length, 'bytes');

          const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: requestBody,
          });

          console.log('📥 Response status:', response.status, response.statusText);

          if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ API Error response:', errorText);
            throw new Error(`API Error: ${response.statusText}`);
          }

          const data = await response.json();
          console.log('✅ Response data received:', data);
          console.log('📊 Response data type:', typeof data);
          
          // Support common Lambda/API Gateway response formats:
          // 1) direct array, 2) JSON string in data.body, 3) object/array in data.body.
          let parsedResults;
          let parsedPersonDetection = null;
          if (Array.isArray(data)) {
            console.log('✅ Data is already an array');
            parsedResults = data;
            const personLabel = data.find(
              (item) => item?.Label && item.Label.toLowerCase() === 'person'
            );
            const inferredPersonCount = Array.isArray(personLabel?.Instances)
              ? personLabel.Instances.length
              : null;
            parsedPersonDetection = {
              personPresent: !!personLabel,
              personConfidence: personLabel ? personLabel.Confidence : null,
              personCount: inferredPersonCount,
            };
          } else if (typeof data.body === 'string') {
            console.log('🔄 Parsing body as JSON string...');
            const parsedBody = JSON.parse(data.body);
            if (Array.isArray(parsedBody)) {
              parsedResults = parsedBody;
              const personLabel = parsedBody.find(
                (item) => item?.Label && item.Label.toLowerCase() === 'person'
              );
              const inferredPersonCount = Array.isArray(personLabel?.Instances)
                ? personLabel.Instances.length
                : null;
              parsedPersonDetection = {
                personPresent: !!personLabel,
                personConfidence: personLabel ? personLabel.Confidence : null,
                personCount: inferredPersonCount,
              };
            } else {
              parsedResults = Array.isArray(parsedBody.labels) ? parsedBody.labels : [];
              parsedPersonDetection = {
                personPresent: !!parsedBody.personPresent,
                personConfidence: parsedBody.personConfidence ?? null,
                personCount: parsedBody.personCount ?? 0,
              };
            }
          } else if (data.body) {
            console.log('✅ Using data.body directly');
            if (Array.isArray(data.body)) {
              parsedResults = data.body;
              const personLabel = data.body.find(
                (item) => item?.Label && item.Label.toLowerCase() === 'person'
              );
              const inferredPersonCount = Array.isArray(personLabel?.Instances)
                ? personLabel.Instances.length
                : null;
              parsedPersonDetection = {
                personPresent: !!personLabel,
                personConfidence: personLabel ? personLabel.Confidence : null,
                personCount: inferredPersonCount,
              };
            } else {
              parsedResults = Array.isArray(data.body.labels) ? data.body.labels : [];
              parsedPersonDetection = {
                personPresent: !!data.body.personPresent,
                personConfidence: data.body.personConfidence ?? null,
                personCount: data.body.personCount ?? 0,
              };
            }
          } else if (Array.isArray(data.labels)) {
            parsedResults = data.labels;
            parsedPersonDetection = {
              personPresent: !!data.personPresent,
              personConfidence: data.personConfidence ?? null,
              personCount: data.personCount ?? 0,
            };
          } else {
            console.error('❌ Unexpected response format:', data);
            throw new Error('Unexpected API response format');
          }

          console.log('✅ Final results to display:', parsedResults);
          setResults(parsedResults);
          setPersonDetection(parsedPersonDetection);
        } catch (err) {
          console.error('❌ Error:', err);
          setError(err.message || 'Failed to analyze image');
        } finally {
          setLoading(false);
        }
      };
      reader.readAsDataURL(image);
    } catch (err) {
      console.error('❌ File reading error:', err);
      setError('Error reading file');
      setLoading(false);
    }
  };

  // Resets the current session so the user can start another detection.
  const handleClear = () => {
    setImage(null);
    setPreview(null);
    setResults(null);
    setPersonDetection(null);
    setError(null);
  };

  return (
    <div className="detection-container">
      <div className="detection-card">
        <h1>Object Detection</h1>
        <p className="subtitle">Upload an image to detect objects and labels</p>

        <div className="content-wrapper">
          {/* Left panel: file upload + request parameters */}
          <div className="left-panel">
            <form onSubmit={handleSubmit} className="upload-form">
              <div className="file-input-wrapper">
                <input
                  type="file"
                  id="image-input"
                  onChange={handleImageSelect}
                  accept="image/*"
                  disabled={loading}
                />
                <label htmlFor="image-input" className="file-label">
                  {image ? `Selected: ${image.name}` : 'Choose an Image'}
                </label>
              </div>

              {preview && (
                <div className="preview-container">
                  <img src={preview} alt="Preview" className="image-preview" />
                </div>
              )}

              <div className="params-container">
                <div className="param-input">
                  <label htmlFor="max-labels">Max Labels:</label>
                  <input
                    type="number"
                    id="max-labels"
                    min="1"
                    max="100"
                    value={maxLabels}
                    onChange={(e) => setMaxLabels(e.target.value)}
                    disabled={loading}
                  />
                </div>
                <div className="param-input">
                  <label htmlFor="confidence">Confidence (%):</label>
                  <input
                    type="number"
                    id="confidence"
                    min="0"
                    max="100"
                    value={confidence}
                    onChange={(e) => setConfidence(e.target.value)}
                    disabled={loading}
                  />
                </div>
              </div>

              <div className="button-group">
                <button type="submit" className="btn btn-primary" disabled={!image || loading}>
                  {loading ? 'Analyzing...' : 'Detect Objects'}
                </button>
                {image && (
                  <button type="button" className="btn btn-secondary" onClick={handleClear}>
                    Clear
                  </button>
                )}
              </div>
            </form>
          </div>

          {/* Right panel: API errors and detection results */}
          <div className="right-panel">
            {error && (
              <div className="alert alert-error">
                <strong>Error:</strong> {error}
              </div>
            )}

            {results && (
              <div className="results-container">
                <h2>
                  Detection Results
                  {Array.isArray(results) ? ` (${results.length})` : ''}
                </h2>
                {personDetection && (
                  <div className={`person-status ${personDetection.personPresent ? 'person-yes' : 'person-no'}`}>
                    <strong>Person detected:</strong> {personDetection.personPresent ? 'Yes' : 'No'}
                    {personDetection.personPresent && personDetection.personConfidence != null && (
                      <span>
                        {' '}
                        (Confidence: {personDetection.personConfidence.toFixed(2)}%
                        {personDetection.personCount != null ? `, Count: ${personDetection.personCount}` : ''})
                      </span>
                    )}
                  </div>
                )}
                {/* Empty array = valid response with no detections */}
                {Array.isArray(results) && results.length === 0 ? (
                  <p className="no-results">No objects detected</p>
                ) : Array.isArray(results) ? (
                  <div className="results-list">
                    {/* Expected item shape: { Label: string, Confidence: number } */}
                    {results.map((result, index) => (
                      <div key={index} className="result-item">
                        <div className="result-label">{result.Label}</div>
                        <div className="result-confidence">
                          <span className="confidence-label">
                            Confidence ({index + 1}/{results.length}):
                          </span>
                          <div className="confidence-bar-container">
                            <div
                              className="confidence-bar"
                              style={{ width: `${result.Confidence}%` }}
                            >
                              <span className="confidence-percentage">
                                {result.Confidence.toFixed(2)}%
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-results">Invalid results format: {JSON.stringify(results)}</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ObjectDetectionUI;
