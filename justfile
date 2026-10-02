formatter:
	. .venv/bin/activate; command black --line-length 125 .

tag:
    git tag v0.1.0 && git push origin v0.1.0