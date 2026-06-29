import ast
from pathlib import Path


TRAIN = Path(__file__).resolve().parents[1] / "src" / "training" / "train.py"


def test_train_cli_supports_eval_file_override_without_importing_training_stack() -> None:
    text = TRAIN.read_text(encoding="utf-8")
    tree = ast.parse(text)
    main_fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")

    assert any(arg.arg == "eval_file" for arg in main_fn.args.args)
    assert '"--eval-file"' in text
    assert "eval_path = Path(eval_file)" in text
