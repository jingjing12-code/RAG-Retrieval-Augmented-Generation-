class ChunkingService:
    def __init__(self, chunk_size=600, overlap=100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_content(self, content, lesson_id, chunk_size=None, overlap=None):
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.overlap
        
        paragraphs = content.split('\n\n')
        chunks = []
        current = ""
        idx = 0

        for para in paragraphs:
            if not para.strip():
                continue
            if len(current) + len(para) > chunk_size and current:
                chunks.append({
                    'lesson_id': lesson_id,
                    'chunk_index': idx,
                    'content': current.strip(),
                    'chunk_metadata': {'chunk_size': len(current)}
                })
                idx += 1
                current = current[-overlap:] + "\n\n" + para
            else:
                current = (current + "\n\n" + para).strip() if current else para

        if current:
            chunks.append({
                'lesson_id': lesson_id,
                'chunk_index': idx,
                'content': current.strip(),
                'chunk_metadata': {'chunk_size': len(current)}
            })

        return chunks