import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# File extensions to include when scanning
SCANNABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".java", ".kt", ".swift",
    ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".rb", ".php", ".sh", ".bash",
    ".yaml", ".yml", ".toml", ".json",
    ".env.example", ".dockerfile",
    ".html", ".css", ".scss", ".sql",
    ".tf", ".hcl",
}

# Directories to always skip
SKIP_DIRS = {
    ".git", ".svn", "__pycache__", "node_modules",
    ".venv", "venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "coverage", ".coverage",
}

# Max file size to read (bytes)
MAX_FILE_SIZE = 100_000

# Max total chars sent to Claude per scan summary
MAX_SCAN_CHARS = 120_000

# Model
MODEL = "claude-opus-4-6"
