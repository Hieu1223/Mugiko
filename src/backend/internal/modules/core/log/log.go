package middleware

import (
	"bytes"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type responseWriter struct {
	http.ResponseWriter
	status      int
	wroteHeader bool
	streaming   bool
	body        bytes.Buffer
}

func (rw *responseWriter) WriteHeader(code int) {
	if rw.wroteHeader {
		return
	}
	rw.status = code
	rw.wroteHeader = true
	rw.streaming = strings.HasPrefix(
		rw.Header().Get("Content-Type"),
		"text/event-stream",
	)
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriter) Write(b []byte) (int, error) {
	if !rw.wroteHeader {
		rw.WriteHeader(http.StatusOK)
	}
	if !rw.streaming {
		rw.body.Write(b)
	}
	return rw.ResponseWriter.Write(b)
}

// Flush lets Server-Sent Events and other streaming handlers flush chunks
// through the logging wrapper.
func (rw *responseWriter) Flush() {
	if !rw.wroteHeader {
		rw.WriteHeader(http.StatusOK)
	}
	if flusher, ok := rw.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

// Unwrap lets http.ResponseController reach the underlying writer.
func (rw *responseWriter) Unwrap() http.ResponseWriter {
	return rw.ResponseWriter
}

func Log(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		wrapped := &responseWriter{
			ResponseWriter: w,
			status:         http.StatusOK,
		}

		next.ServeHTTP(wrapped, r)

		duration := time.Since(start)

		logLine := fmt.Sprintf("INFO:\t %s - \"%s %s %s\" %d %s - %.3fms",
			r.RemoteAddr,
			r.Method,
			r.URL.Path,
			r.Proto,
			wrapped.status,
			http.StatusText(wrapped.status),
			float64(duration.Microseconds())/1000.0,
		)

		fmt.Printf("%s\n", logLine)

		if wrapped.status >= 400 {
			errMsg := wrapped.body.String()
			logErrorToFile(logLine, errMsg)
		}
	})
}

func logErrorToFile(logLine, errMsg string) {
	logDir := os.Getenv("LOG_DIR")
	if logDir == "" {
		logDir = "./logs"
	}

	if err := os.MkdirAll(logDir, 0755); err != nil {
		fmt.Printf("ERROR: failed to create log directory: %v\n", err)
		return
	}

	logFile := filepath.Join(logDir, "error.log")
	f, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Printf("ERROR: failed to open log file: %v\n", err)
		return
	}
	defer f.Close()

	timestamp := time.Now().Format("2006-01-02 15:04:05")
	f.WriteString(fmt.Sprintf("[%s] %s | %s\n", timestamp, logLine, errMsg))
}
