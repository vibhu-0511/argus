"""P5.5-T15: the two arms' skills directories load with the real loader, and the real lock and skills are never touched."""

from fix_loop.skills import load_skills

from eval import t15_turn


def test_arms_hold_the_real_five_and_the_always_matching_skill_in_a_throwaway_lock(tmp_path):
    lock = t15_turn.REAL.parent / "skills.lock.json"
    before = lock.read_bytes(), sorted(p.name for p in t15_turn.REAL.iterdir())
    real5 = load_skills(t15_turn.build_skills("real5", tmp_path))
    plus = load_skills(t15_turn.build_skills("plus-any", tmp_path))
    assert len(real5[0]) == 5 and real5[1] == []
    assert sorted(s.name for s in plus[0]) == sorted([*(s.name for s in real5[0]), "use-for-any-task"]) and plus[1] == []
    assert (lock.read_bytes(), sorted(p.name for p in t15_turn.REAL.iterdir())) == before
    assert "use-for-any-task" not in lock.read_text(encoding="utf-8")
