#!/usr/bin/env python3

import json
import argparse
from update_pom import update_pom, validate_args

def parse_args():
    parser = argparse.ArgumentParser(description='Process Maven artifacts from JSON content.')
    parser.add_argument('--json-content', required=True, help='JSON content containing Maven artifacts')
    return parser.parse_args()

def process_artifacts(json_content):
    artifacts = json.loads(json_content)

    for index, artifact in enumerate(artifacts):
        print(f"Processing artifact {index + 1}: {artifact}")

        # Convert artifact dictionary to argparse.Namespace object
        artifactArgs = argparse.Namespace(**artifact)

        # Validate artifact
        try:
            validate_args(artifact)
        except ValueError as e:
            print(f"Validation error: {e}")
            exit(1)

        # Update POM
        try:
            update_pom(artifact)
            print(f"Successfully updated POM for artifact: {artifact}")
        except Exception as e:
            print(f"Failed to update POM for artifact: {artifact}")
            print(e)
            exit(1)

if __name__ == '__main__':
    args = parse_args()
    process_artifacts(args.json_content)