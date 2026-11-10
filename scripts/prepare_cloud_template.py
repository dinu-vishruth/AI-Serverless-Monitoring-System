"""Merge current SAM infrastructure into verified build artifacts for an upgrade.

Run after `sam build` and before `sam package`. Existing imported log groups
keep their literal names so CloudFormation does not propose replacement when
switching between a literal name and an intrinsic expression.
"""
import argparse
import json
from pathlib import Path
import subprocess

import yaml


class CloudFormationDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stack-name', required=True)
    parser.add_argument('--region', default='ap-south-2')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    built_path = root / '.aws-sam' / 'build' / 'template.yaml'
    template = yaml.safe_load((root / 'template.yaml').read_text(encoding='utf-8'))
    built = yaml.safe_load(built_path.read_text(encoding='utf-8'))
    result = subprocess.run([
        'aws', 'cloudformation', 'list-stack-resources', '--stack-name', args.stack_name,
        '--region', args.region, '--output', 'json', '--no-cli-pager',
    ], check=True, capture_output=True, text=True)
    existing = {r['LogicalResourceId']: r for r in json.loads(result.stdout)['StackResourceSummaries']}
    for name, resource in template['Resources'].items():
        for prop in ('CodeUri', 'ContentUri'):
            if prop in resource.get('Properties', {}):
                resource['Properties'][prop] = built['Resources'][name]['Properties'][prop]
    for name in ('ApiFunctionLogGroup', 'HealthCheckerFunctionLogGroup'):
        if name in existing:
            template['Resources'][name]['Properties']['LogGroupName'] = existing[name]['PhysicalResourceId']
            function = name.removesuffix('LogGroup')
            template['Resources'][function]['Properties']['LoggingConfig'] = {'LogGroup': existing[name]['PhysicalResourceId']}
    built_path.write_text(yaml.dump(template, Dumper=CloudFormationDumper, sort_keys=False), encoding='utf-8')
    print('Prepared upgrade template; existing imported log-group names preserved.')


if __name__ == '__main__':
    main()
