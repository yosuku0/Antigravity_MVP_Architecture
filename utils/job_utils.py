from pathlib import Path

def get_job_path(job_id: str) -> Path:
    """
    JOB ID から work/jobs/ 下の物理パスを特定する。
    ID に拡張子が含まれていない場合は .md を付加。
    """
    jobs_dir = Path("work/jobs")
    # 1. {jobs_dir}/{job_id}
    job_path = jobs_dir / job_id
    if job_path.exists():
        return job_path
    
    # 2. {jobs_dir}/{job_id}.md
    if not job_id.endswith(".md"):
        job_path = jobs_dir / f"{job_id}.md"
        if job_path.exists():
            return job_path
            
    # 3. job_id 自体が絶対パスまたは相対パスとして存在する場合
    direct_path = Path(job_id)
    if direct_path.exists():
        return direct_path
        
    return jobs_dir / f"{job_id}.md" # Fallback
