"""Build a draft customer-server transfer bundle from an existing exact release.

Images must already be built/present locally. This command never pulls/builds an
image or downloads dependencies/models. It does not deploy the application.
"""
import argparse
import importlib.util
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release-id', required=True)
    parser.add_argument('--app-image', required=True)
    parser.add_argument('--nginx-image', required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('customer_bundle', Path(__file__).resolve().parents[1]/'deploy/customer/customer.py')
    customer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(customer)
    try:
        result = customer.build_package(args.repository, args.output, args.release_id, args.app_image, args.nginx_image)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
