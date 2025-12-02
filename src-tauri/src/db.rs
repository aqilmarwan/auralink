use rusqlite::{params, Connection};
use std::path::PathBuf;

pub fn db_path() -> PathBuf {
    // Prefer platform app-local data dir; fallback to temp dir
    let base_dir = dirs::data_local_dir().unwrap_or(std::env::temp_dir());
    let app_dir = base_dir.join("auralink");
    let _ = std::fs::create_dir_all(&app_dir);
    app_dir.join("auralink.sqlite")
}

pub fn init() -> rusqlite::Result<()> {
    let conn = Connection::open(db_path())?;
    conn.execute_batch(
        r#"
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS files (
          id TEXT PRIMARY KEY,
          name TEXT,
          path TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          file_id TEXT NOT NULL,
          text TEXT NOT NULL,
          is_user_message INTEGER NOT NULL,
          created_at TEXT NOT NULL
        );
        "#,
    )?;
    // Best-effort schema evolution for thumbnail path
    let _ = conn.execute("ALTER TABLE files ADD COLUMN thumb_path TEXT", []);
    let _ = conn.execute("ALTER TABLE files ADD COLUMN name TEXT", []);
    Ok(())
}

pub fn insert_message(
    id: &str,
    file_id: &str,
    text: &str,
    is_user: bool,
    created_at: &str,
) -> rusqlite::Result<()> {
    let conn = Connection::open(db_path())?;
    conn.execute(
        "INSERT INTO messages (id,file_id,text,is_user_message,created_at) VALUES (?,?,?,?,?)",
        params![id, file_id, text, is_user as i32, created_at],
    )?;
    Ok(())
}

pub fn insert_file(id: &str, name: &str, path: &str, created_at: &str) -> rusqlite::Result<()> {
    let conn = Connection::open(db_path())?;
    conn.execute(
        "INSERT INTO files (id, name, path, created_at) VALUES (?, ?, ?, ?)",
        params![id, name, path, created_at],
    )?;
    Ok(())
}

pub fn get_file_path(id: &str) -> rusqlite::Result<Option<String>> {
    let conn = Connection::open(db_path())?;
    let mut stmt = conn.prepare("SELECT path FROM files WHERE id=?1 LIMIT 1")?;
    let mut rows = stmt.query(params![id])?;
    if let Some(row) = rows.next()? {
        let path: String = row.get(0)?;
        Ok(Some(path))
    } else {
        Ok(None)
    }
}

#[derive(Debug, Clone)]
pub struct FileRow {
    pub id: String,
    pub name: Option<String>,
    pub path: String,
    pub thumb_path: Option<String>,
    pub created_at: String,
}

pub fn list_files() -> rusqlite::Result<Vec<FileRow>> {
    let conn = Connection::open(db_path())?;
    let mut stmt = conn.prepare("SELECT id, name, path, thumb_path, created_at FROM files ORDER BY created_at DESC")?;
    let rows = stmt.query_map([], |r| {
        Ok(FileRow {
            id: r.get(0)?,
            name: r.get(1).ok(),
            path: r.get(2)?,
            thumb_path: r.get(3).ok(),
            created_at: r.get(4)?,
        })
    })?;
    Ok(rows.filter_map(Result::ok).collect())
}

pub fn delete_file(id: &str) -> rusqlite::Result<()> {
    let conn = Connection::open(db_path())?;
    conn.execute("DELETE FROM messages WHERE file_id=?1", params![id])?;
    conn.execute("DELETE FROM files WHERE id=?1", params![id])?;
    Ok(())
}

pub fn set_file_thumb(id: &str, thumb_path: &str) -> rusqlite::Result<()> {
    let conn = Connection::open(db_path())?;
    conn.execute(
        "UPDATE files SET thumb_path=?2 WHERE id=?1",
        params![id, thumb_path],
    )?;
    Ok(())
}

pub struct Page {
  pub messages: Vec<serde_json::Value>,
  pub next_cursor: Option<String>,
}

pub fn list_messages(file_id: &str, limit: i64, cursor: Option<&str>) -> rusqlite::Result<Page> {
    let conn = Connection::open(db_path())?;
    // Pagination based on created_at for stable chronological ordering (RFC3339 sorts lexicographically)
    let after = cursor.unwrap_or("");
    let mut stmt = conn.prepare(
        "SELECT id,text,is_user_message,created_at
         FROM messages
         WHERE file_id=?1 AND created_at > ?2
         ORDER BY created_at ASC
         LIMIT ?3",
    )?;
    let rows = stmt.query_map(params![file_id, after, limit + 1], |r| {
        Ok(serde_json::json!({
            "id": r.get::<_, String>(0)?,
            "text": r.get::<_, String>(1)?,
            "isUserMessage": (r.get::<_, i32>(2)? != 0),
            "createdAt": r.get::<_, String>(3)?,
        }))
    })?;

    let mut items: Vec<serde_json::Value> = rows.filter_map(Result::ok).collect();
    let next_cursor = if (items.len() as i64) > limit {
        // Use the last item's createdAt as the cursor for the next page
        let last = items
            .pop()
            .and_then(|v| v.get("createdAt").cloned())
            .and_then(|v| v.as_str().map(String::from));
        last
    } else { None };

    Ok(Page { messages: items, next_cursor })
}