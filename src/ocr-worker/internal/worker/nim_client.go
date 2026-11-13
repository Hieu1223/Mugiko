package worker

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type parseResult struct {
	Content      string     `json:"content"`
	FinishReason string     `json:"finish_reason"`
	Usage        parseUsage `json:"usage"`
}

type parseUsage struct {
	OutputTokens int `json:"output_tokens"`
}

type NIMError struct {
	msg string
}

func (e *NIMError) Error() string { return e.msg }

type NIMClient struct {
	apiKeys  []string
	keyIdx   int
	baseURL  string
	timeout  time.Duration
	http     *http.Client
	maxImage int64
}

func NewNIMClient(apiKeys []string, baseURL string, timeout time.Duration, maxImage int64) (*NIMClient, error) {
	if len(apiKeys) == 0 {
		return nil, errors.New("api_keys must not be empty")
	}
	if strings.TrimSpace(baseURL) == "" {
		baseURL = defaultNIMParseURL
	}
	baseURL = strings.TrimRight(baseURL, "/")
	return &NIMClient{
		apiKeys:  apiKeys,
		baseURL:  baseURL,
		timeout:  timeout,
		maxImage: maxImage,
		keyIdx:   0,
		http:     &http.Client{Timeout: timeout},
	}, nil
}

func (c *NIMClient) nextKey() string {
	key := c.apiKeys[c.keyIdx]
	c.keyIdx = (c.keyIdx + 1) % len(c.apiKeys)
	return key
}

// imageContentType sniffs the image MIME type from the first bytes of body.
func imageContentType(body []byte) string {
	t := http.DetectContentType(body)
	switch t {
	case "image/jpeg", "image/png", "image/webp":
		return t
	default:
		return "application/octet-stream"
	}
}

// extensionFromURL returns a safe file extension for the document part.
func extensionFromURL(url string) string {
	ext := strings.ToLower(filepathExt(url))
	switch ext {
	case ".jpg", ".jpeg", ".png", ".webp":
		return ext
	default:
		return ".jpg"
	}
}

func filepathExt(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '/' {
			return ""
		}
		if path[i] == '.' {
			return path[i:]
		}
	}
	return ""
}

func (c *NIMClient) ParseDocument(ctx context.Context, imageURL string, maxTokens int) (string, error) {
	// Download the image.
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, imageURL, nil)
	if err != nil {
		return "", err
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return "", fmt.Errorf("download image: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("download image HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("read image: %w", err)
	}
	if int64(len(body)) > c.maxImage {
		return "", fmt.Errorf("image too large: %d bytes", len(body))
	}
	ctype := imageContentType(body)
	if ctype == "application/octet-stream" {
		return "", errors.New("unsupported image type: could not detect image/jpeg or image/png")
	}

	const maxAttempts = 3
	const retryDelay = 1 * time.Second
	retryable := map[int]bool{429: true, 500: true, 502: true, 503: true, 504: true}

	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		boundary := fmt.Sprintf("----MugikoOCRBoundary%d", time.Now().UnixNano())
		bodyBuf := &bytes.Buffer{}

		// document part
		bodyBuf.WriteString("--" + boundary + "\r\n")
		bodyBuf.WriteString(fmt.Sprintf("Content-Disposition: form-data; name=\"document\"; filename=\"document%s\"\r\n", extensionFromURL(imageURL)))
		bodyBuf.WriteString(fmt.Sprintf("Content-Type: %s\r\n\r\n", ctype))
		bodyBuf.Write(body)
		bodyBuf.WriteString("\r\n")

		// options part
		options := fmt.Sprintf(`{"decoding":{"max_output_tokens":%d}}`, maxTokens)
		bodyBuf.WriteString("--" + boundary + "\r\n")
		bodyBuf.WriteString("Content-Disposition: form-data; name=\"options\"\r\n")
		bodyBuf.WriteString("Content-Type: application/json\r\n\r\n")
		bodyBuf.WriteString(options)
		bodyBuf.WriteString("\r\n")
		bodyBuf.WriteString("--" + boundary + "--\r\n")

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL, bodyBuf)
		if err != nil {
			return "", err
		}
		req.Header.Set("Authorization", "Bearer "+c.nextKey())
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Content-Type", "multipart/form-data; boundary="+boundary)

		resp, err := c.http.Do(req)
		if err != nil {
			lastErr = fmt.Errorf("nim request failed: %w", err)
			if attempt < maxAttempts {
				select {
				case <-time.After(retryDelay):
				case <-ctx.Done():
					return "", ctx.Err()
				}
				continue
			}
			return "", lastErr
		}

		respBody, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if retryable[resp.StatusCode] {
			lastErr = &NIMError{fmt.Sprintf("nim HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))}
			if attempt < maxAttempts {
				select {
				case <-time.After(retryDelay):
				case <-ctx.Done():
					return "", ctx.Err()
				}
				continue
			}
			return "", lastErr
		}

		if resp.StatusCode >= 400 {
			return "", &NIMError{fmt.Sprintf("nim HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))}
		}

		var result parseResult
		if err := json.Unmarshal(respBody, &result); err != nil {
			// Not JSON; return raw body as the stored result.
			return string(respBody), nil
		}
		out, _ := json.Marshal(result)
		return string(out), nil
	}
	return "", lastErr
}
