import os

# ── Gunicorn config ───────────────────────────────────────────────────────────
workers      = 1          # Only 1 worker needed for webhook bot
threads      = 4          # Handle concurrent requests within the worker
timeout      = 120        # Long timeout for slow NASA API calls
bind         = f"0.0.0.0:{os.environ.get('PORT', 10000)}"
worker_class = "sync"

def post_fork(server, worker):
    """
    Called in each worker process AFTER fork().
    Threads don't survive fork, so we must start the bot loop HERE,
    inside the actual worker process, not in the master.
    """
    import main
    main.init_worker()
