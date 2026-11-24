# Lessons (Dersler)

Reusable traps — recurring, non-obvious, root-caused. One line each; check here
before debugging blind. One-off bugs are not lessons.

## Backend

- (none yet)

## Frontend

- (none yet)

## Infra / DevEx

- `docker compose up` var olan imajı kullanır — kod değişikliği sonrası
  `up -d --build` şart, yoksa arayüz/API eski kodla gelir. Doğrulama:
  `docker compose ps` + `curl 127.0.0.1:$WEB_PORT`.
