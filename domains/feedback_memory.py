import os
import json
import threading
import faiss
import numpy as np
from pathlib import Path
from datetime import datetime
from sentence_transformers import SentenceTransformer
from utils.logging_config import get_logger

logger = get_logger("feedback_memory")

class FeedbackMemory:
    """
    人間からの Reject フィードバックを多言語ベクトル化して蓄積・検索するクラス。
    コサイン類似度による検索と、並列実行下でのスレッドセーフな永続化を保証する。
    """
    
    def __init__(self, storage_dir="work/memory"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.storage_dir / "lessons.index"
        self.meta_path = self.storage_dir / "lessons_meta.json"
        
        # 多言語対応モデルのロード
        logger.info("Loading sentence-transformer model: paraphrase-multilingual-MiniLM-L12-v2")
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.dimension = 384
        
        # 排他制御用ロック
        self.lock = threading.Lock()
        
        # インデックスとメタデータの初期化
        self.index = self._load_index()
        self.metadata = self._load_metadata()

    def _load_index(self):
        if self.index_path.exists():
            try:
                return faiss.read_index(str(self.index_path))
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
        # コサイン類似度（内積）用のインデックスを初期化
        return faiss.IndexFlatIP(self.dimension)

    def _load_metadata(self):
        if self.meta_path.exists():
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load metadata: {e}")
        return []

    def add_lesson(self, task_description: str, feedback: str, job_id: str):
        """タスクとフィードバックのペアをスレッドセーフに保存"""
        if not task_description or not feedback:
            return

        # 1. 埋め込み生成と L2 正規化 (コサイン類似度用)
        embedding = self.model.encode([task_description])[0].astype('float32')
        embedding_arr = np.array([embedding])
        faiss.normalize_L2(embedding_arr)
        
        with self.lock:
            # 2. FAISS インデックスに追加
            self.index.add(embedding_arr)
            
            # 3. メタデータの追記
            self.metadata.append({
                "job_id": job_id,
                "task": task_description,
                "feedback": feedback,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            
            # 4. 物理ファイルへの永続化
            self._save()
            logger.info(f"Learned new lesson from job {job_id}", extra={"job_id": job_id})

    def search_lessons(self, current_task: str, top_k=3, threshold=0.5) -> list[str]:
        """現在のタスクに類似した過去の教訓を検索 (閾値以上のものを返す)"""
        if not current_task or self.index.ntotal == 0:
            return []

        # 1. クエリの埋め込み生成と正規化
        query_vector = self.model.encode([current_task])[0].astype('float32')
        query_arr = np.array([query_vector])
        faiss.normalize_L2(query_arr)
        
        # 2. 内積検索 (正規化済みなのでコサイン類似度と同等)
        distances, indices = self.index.search(query_arr, top_k)

        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx == -1: continue
            
            # コサイン類似度が閾値以上なら採用
            if score > threshold: 
                meta = self.metadata[idx]
                results.append(
                    f"Past Task: {meta['task']}\n"
                    f"   -> Lesson: {meta['feedback']} (Similarity: {score:.2f})"
                )
        
        return results

    def _save(self):
        """インデックスとメタデータを物理ファイルに保存"""
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

# Singleton Instance Management
_memory_instance = None

def get_feedback_memory() -> FeedbackMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = FeedbackMemory()
    return _memory_instance
