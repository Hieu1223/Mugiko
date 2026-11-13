package dto

type AuthType string

const (
	AuthTypeFirebase  AuthType = "firebase"
	AuthTypeAdmin     AuthType = "admin"
	AuthTypeAnonymous AuthType = "anonymous"
	AuthTypeSystem    AuthType = "system"
)

type Role string

const (
	RoleAnonymous Role = "anonymous"
	RoleUser      Role = "user"
	RoleAdmin     Role = "admin"
)