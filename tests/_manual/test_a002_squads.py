import yaml
from pathlib import Path

def test_a002_squads():
    squads_dir = Path(__file__).resolve().parents[2] / "apps" / "crew" / "squads"
    squads = ["coding_squad", "research_squad", "review_squad"]
    
    for squad in squads:
        squad_path = squads_dir / squad
        assert squad_path.exists(), f"Squad directory {squad} missing"
        
        roles_file = squad_path / "roles.yaml"
        tasks_file = squad_path / "tasks.yaml"
        
        assert roles_file.exists(), f"roles.yaml missing for {squad}"
        assert tasks_file.exists(), f"tasks.yaml missing for {squad}"
        
        with open(roles_file) as f:
            roles = yaml.safe_load(f)
            assert isinstance(roles, dict), f"roles.yaml for {squad} is not a dict"
            assert len(roles) >= 1, f"roles.yaml for {squad} is empty"
            
        with open(tasks_file) as f:
            tasks = yaml.safe_load(f)
            assert isinstance(tasks, dict), f"tasks.yaml for {squad} is not a dict"
            assert len(tasks) >= 1, f"tasks.yaml for {squad} is empty"

    print("A-002 Squads Structure Test: PASSED")

if __name__ == "__main__":
    test_a002_squads()
