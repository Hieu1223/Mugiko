package persistent

import (
	"database/sql"
	"errors"
	"time"

	"github.com/google/uuid"
)

type Conversation struct {
	ID        uuid.UUID `json:"id"`
	UserID    string    `json:"user_id"`
	Title     string    `json:"title"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

type Message struct {
	ID                 uuid.UUID  `json:"id"`
	ConversationID     uuid.UUID  `json:"conversation_id"`
	Role               string     `json:"role"`
	Content            string     `json:"content"`
	Status             string     `json:"status"`
	Error              *string    `json:"error,omitempty"`
	AssistantMessageID *uuid.UUID `json:"assistant_message_id,omitempty"`
	Metadata           map[string]any `json:"metadata"`
	CreatedAt          time.Time  `json:"created_at"`
	UpdatedAt          time.Time  `json:"updated_at"`
}

var ErrConversationNotFound = errors.New("conversation not found")

type ConversationRepository struct {
	db *sql.DB
}

func NewConversationRepository(db *sql.DB) *ConversationRepository {
	return &ConversationRepository{db: db}
}

func (r *ConversationRepository) Create(userID, title string) (*Conversation, error) {
	id := uuid.New()
	now := time.Now()
	_, err := r.db.Exec(`INSERT INTO conversations (id,user_id,title,created_at,updated_at) VALUES ($1,$2,$3,$4,$5)`,
		id.String(), userID, title, now, now)
	if err != nil {
		return nil, err
	}
	return &Conversation{ID: id, UserID: userID, Title: title, CreatedAt: now, UpdatedAt: now}, nil
}

func (r *ConversationRepository) ListByUser(userID string) ([]Conversation, error) {
	rows, err := r.db.Query(`SELECT id,user_id,title,created_at,updated_at FROM conversations WHERE user_id=$1 ORDER BY updated_at DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Conversation
	for rows.Next() {
		var c Conversation
		var id string
		if err := rows.Scan(&id, &c.UserID, &c.Title, &c.CreatedAt, &c.UpdatedAt); err != nil {
			return nil, err
		}
		u, _ := uuid.Parse(id)
		c.ID = u
		out = append(out, c)
	}
	return out, rows.Err()
}

func (r *ConversationRepository) GetByID(id uuid.UUID) (*Conversation, error) {
	var c Conversation
	var uid string
	err := r.db.QueryRow(`SELECT id,user_id,title,created_at,updated_at FROM conversations WHERE id=$1`, id.String()).
		Scan(&uid, &c.UserID, &c.Title, &c.CreatedAt, &c.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrConversationNotFound
	}
	if err != nil {
		return nil, err
	}
	u, _ := uuid.Parse(uid)
	c.ID = u
	return &c, nil
}

func (r *ConversationRepository) Delete(id uuid.UUID) error {
	_, err := r.db.Exec(`DELETE FROM conversations WHERE id=$1`, id.String())
	return err
}

func (r *ConversationRepository) AddMessage(convID uuid.UUID, role, content string, status string) (*Message, error) {
	id := uuid.New()
	now := time.Now()
	if status == "" {
		status = "completed"
	}
	_, err := r.db.Exec(`INSERT INTO messages (id,conversation_id,role,content,status,created_at,updated_at) VALUES ($1,$2,$3,$4,$5,$6,$7)`,
		id.String(), convID.String(), role, content, status, now, now)
	if err != nil {
		return nil, err
	}
	return &Message{ID: id, ConversationID: convID, Role: role, Content: content, Status: status, CreatedAt: now, UpdatedAt: now}, nil
}

func (r *ConversationRepository) GetMessage(id uuid.UUID) (*Message, error) {
	var m Message
	var mid, cid string
	err := r.db.QueryRow(`SELECT id,conversation_id,role,content,status,created_at,updated_at FROM messages WHERE id=$1`, id.String()).
		Scan(&mid, &cid, &m.Role, &m.Content, &m.Status, &m.CreatedAt, &m.UpdatedAt)
	if err != nil {
		return nil, err
	}
	u, _ := uuid.Parse(mid)
	c, _ := uuid.Parse(cid)
	m.ID = u
	m.ConversationID = c
	return &m, nil
}

func (r *ConversationRepository) ListMessages(convID uuid.UUID) ([]Message, error) {
	rows, err := r.db.Query(`SELECT id,conversation_id,role,content,status,created_at,updated_at FROM messages WHERE conversation_id=$1 ORDER BY created_at ASC`, convID.String())
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Message
	for rows.Next() {
		var m Message
		var id, cid string
		if err := rows.Scan(&id, &cid, &m.Role, &m.Content, &m.Status, &m.CreatedAt, &m.UpdatedAt); err != nil {
			return nil, err
		}
		u, _ := uuid.Parse(id)
		c, _ := uuid.Parse(cid)
		m.ID = u
		m.ConversationID = c
		out = append(out, m)
	}
	return out, rows.Err()
}
