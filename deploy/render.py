"""Fill the placeholders in `deploy/iam/*.json` and print the result.

    python deploy/render.py trust-policy --account 123456789012
    python deploy/render.py execution-policy --region us-west-2 --ecr-repo anchor

WHY THE TEMPLATES CARRY PLACEHOLDERS. An IAM policy is mostly ARNs, and an ARN contains the account
id. Committing a rendered policy publishes that account id to anyone who reads the repository -- it
is not a credential, but it is an identifier that makes a target easier to name, and there is no
reason for it to be in version control when a placeholder does the same job.

The account id defaults to whatever the current AWS credentials resolve to, so the ordinary case
needs no arguments at all and nobody has to type it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def current_account() -> str:
    """The account the ambient credentials belong to, via the AWS CLI.

    The CLI rather than boto3 on purpose: this is a deployment script run by a person who already
    has the CLI configured, and it keeps the repo's Python dependencies out of the question.
    """
    try:
        out = subprocess.run(["aws", "sts", "get-caller-identity", "--query", "Account",
                              "--output", "text"],
                             capture_output=True, text=True, check=True, shell=False)
    except (OSError, subprocess.CalledProcessError) as e:
        raise SystemExit(
            "could not determine the AWS account id, and --account was not given.\n"
            f"`aws sts get-caller-identity` failed: {e}") from e
    return out.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("template", choices=("trust-policy", "execution-policy"))
    ap.add_argument("--account", default=None, help="AWS account id (default: the current one)")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--ecr-repo", default="anchor", help="the ECR repository holding the image")
    ap.add_argument("--agent-name", default="anchor", help="the AgentCore Runtime name")
    ap.add_argument("-o", "--out", type=Path, default=None,
                    help="write here instead of stdout")
    args = ap.parse_args()

    text = (HERE / "iam" / f"{args.template}.json").read_text(encoding="utf-8")
    for placeholder, value in (("<account-id>", args.account or current_account()),
                               ("<region>", args.region),
                               ("<ecr-repo>", args.ecr_repo),
                               ("<agent-name>", args.agent_name)):
        text = text.replace(placeholder, value)

    # Parse before emitting. A policy that is not valid JSON fails in the middle of an `aws iam`
    # call with a message about the request rather than about the file, which is a bad place to
    # find out -- and a leftover placeholder would sail through as a literal ARN segment.
    json.loads(text)
    if "<" in text:
        raise SystemExit(f"a placeholder was left unfilled:\n{text}")

    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
