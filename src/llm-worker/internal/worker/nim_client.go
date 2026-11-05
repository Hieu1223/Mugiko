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

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatRequest struct {
	Model       string        `json:"model"`
	Messages    []chatMessage `json:"messages"`
	Temperature float64       `json:"temperature"`
	MaxTokens   int           `json:"max_tokens"`
	Stream      bool          `json:"stream"`
}

type chatResponse struct {
	Choices []choice `json:"choices"`
}

type choice struct {
	Message chatMessage `json:"message"`
}

type NIMError struct {
	msg string
}

func (e *NIMError) Error() string { return e.msg }

type NIMClient struct {
	apiKeys     []string
	keyIndex    int
	baseURL     string
	model       string
	temperature float64
	maxTokens   int
	timeout     time.Duration
	http        *http.Client
}

func NewNIMClient(apiKeys []string, baseURL, model string, temperature float64, maxTokens int, timeout time.Duration) (*NIMClient, error) {
	if len(apiKeys) == 0 {
		return nil, errors.New("api_keys must not be empty")
	}
	if strings.TrimSpace(baseURL) == "" {
		baseURL = "https://integrate.api.nvidia.com/v1"
	}
	baseURL = strings.TrimRight(baseURL, "/")
	return &NIMClient{
		apiKeys:    apiKeys,
		baseURL:    baseURL,
		model:      model,
		temperature: temperature,
		maxTokens:   maxTokens,
		timeout:     timeout,
		keyIndex:    0,
		http:        &http.Client{Timeout: timeout},
	}, nil
}

func (c *NIMClient) nextKey() string {
	key := c.apiKeys[c.keyIndex]
	c.keyIndex = (c.keyIndex + 1) % len(c.apiKeys)
	return key
}

func (c *NIMClient) Chat(ctx context.Context, messages []chatMessage) (string, error) {
	const maxAttempts = 3
	const retryDelay = 1 * time.Second
	retryable := map[int]bool{429: true, 500: true, 502: true, 503: true, 504: true}

	var lastErr error
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		reqBody, err := json.Marshal(chatRequest{
			Model:       c.model,
			Messages:    messages,
			Temperature: c.temperature,
			MaxTokens:   c.maxTokens,
			Stream:      false,
		})
		if err != nil {
			return "", err
		}

		req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/chat/completions", bytes.NewReader(reqBody))
		if err != nil {
			return "", err
		}
		req.Header.Set("Authorization", "Bearer "+c.nextKey())
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")

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

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		if retryable[resp.StatusCode] {
			lastErr = &NIMError{fmt.Sprintf("nim HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))}
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
			return "", &NIMError{fmt.Sprintf("nim HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))}
		}

		var chatResp chatResponse
		if err := json.Unmarshal(body, &chatResp); err != nil {
			return "", &NIMError{"nim returned a non-json response"}
		}
		if len(chatResp.Choices) == 0 || strings.TrimSpace(chatResp.Choices[0].Message.Content) == "" {
			return "", &NIMError{"nim returned an empty response"}
		}
		return chatResp.Choices[0].Message.Content, nil
	}
	return "", lastErr
}
