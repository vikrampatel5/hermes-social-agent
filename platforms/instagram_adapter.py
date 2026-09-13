from platforms.base import ContentItem

class InstagramAdapter:
    def __init__(self, config): pass
    def init(self): return False
    async def search(self, query, max_results=10): return []
    def is_healthy(self): return False
    def health_check(self): return False
