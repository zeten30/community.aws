#!/usr/bin/python
"""
Copyright (c) 2017 Ansible Project
GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = '''
---
module: aws_s3_bucket_info
version_added: 1.0.0
author: "Gerben Geijteman (@hyperized)"
short_description: Lists S3 buckets in AWS
requirements:
  - boto3 >= 1.4.4
  - python >= 2.6
description:
    - Lists S3 buckets in AWS
    - This module was called C(aws_s3_bucket_facts) before Ansible 2.9, returning C(ansible_facts).
      Note that the M(community.aws.aws_s3_bucket_info) module no longer returns C(ansible_facts)!
options:
  name:
    description:
      - Get info only about specified bucket
    type: str
    default: ""
  name_filter:
    description:
      - Get info only about buckets name matching defined string
    type: str
    default: ""
  bucket_facts:
    description:
      - Retrieve requested S3 bucket detailed information
      - Each bucket_X option executes one API call, hence many options=true will case slower module execution
      - You can limit buckets by using I(name) or I(name_filter) option 
    suboptions:
      bucket_location:
        description: Retrive S3 bucket location
        type: bool
        default: False
      bucket_replication:
        description: Retrive S3 bucket replication
        type: bool
        default: False
      bucket_acl:
        description: Retrive S3 bucket ACLs
        type: bool
        default: False
      bucket_logging:
        description: Retrive S3 bucket logging
        type: bool
        default: False
      bucket_request_payment:
        description: Retrive S3 bucket request payment
        type: bool
        default: False
      bucket_analytics_configuration:
        description: Retrive S3 bucket analytics configuration
        type: bool
        default: False
      bucket_tagging:
        description: Retrive S3 bucket tagging
        type: bool
        default: False
      bucket_cors:
        description: Retrive S3 bucket CORS configuration
        type: bool
        default: False
      bucket_notification_configuration:
        description: Retrive S3 bucket notification configuration
        type: bool
        default: False
      bucket_encryption:
        description: Retrive S3 bucket encryption
        type: bool
        default: False
      bucket_ownership_controls:
        description: Retrive S3 ownership controls
        type: bool
        default: False
      bucket_website:
        description: Retrive S3 bucket website
        type: bool
        default: False
      bucket_policy:
        description: Retrive S3 bucket policy
        type: bool
        default: False
      bucket_policy_status:
        description: Retrive S3 bucket policy status
        type: bool
        default: False
      bucket_lifecycle_configuration:
        description: Retrive S3 bucket lifecycle configuration
        type: bool
        default: False
      public_access_block:
        description: Retrive S3 bucket public access block
        type: bool
        default: False
    type: dict
  transform_location:
    description:
      - S3 bucket location for default us-east-1 is normally reported as 'null'
      - setting this option to 'true' will return 'us-east-1' instead
      - affects only queries with I(bucket_facts) > I(bucket_location) = true
    type: bool
    default: False

extends_documentation_fragment:
- amazon.aws.aws
- amazon.aws.ec2

'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Note: Only AWS S3 is currently supported

# Lists all s3 buckets
- community.aws.aws_s3_bucket_info:
  register: result

# Retrieve detailed bucket information
- community.aws.aws_s3_bucket_info:
    # Show only buckets with name matching
    name_filter: your.testing
    # Choose facts to retrieve
    bucket_facts:
      # bucket_accelerate_configuration: true
      bucket_acl: true
      bucket_cors: true
      bucket_encryption: true
      # bucket_lifecycle_configuration: true
      bucket_location: true
      # bucket_logging: true
      # bucket_notification_configuration: true
      # bucket_ownership_controls: true
      # bucket_policy: true
      # bucket_policy_status: true
      # bucket_replication: true
      # bucket_request_payment: true
      # bucket_tagging: true
      # bucket_website: true
      # public_access_block: true
    transform_location: true
    register: result

# Print out result
- name: List buckets
  ansible.builtin.debug:
    msg: "{{ result['buckets'] }}"
'''

RETURN = '''
buckets:
  description: "List of buckets"
  returned: always
  sample:
    - creation_date: '2017-07-06 15:05:12 +00:00'
      name: my_bucket
      # bucket facts if requested
      bucket_location: dictionary data
      bucket_cors: dictionary data
      # ...etc

# if name options was specified
bucket_name: 
  description: "Name of the bucket requested"
  sample: "my_bucket"

# if name_filter was specified
bucket_name_filter: 
  description: "String to match bucket name"
  sample: "buckets_prefix"
'''

try:
    import botocore
except ImportError:
    pass  # Handled by AnsibleAWSModule

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.core import AnsibleAWSModule


def get_bucket_list(module, connection, name="", name_filter=""):
    """
    Return result of list_buckets json encoded
    Filter only buckets matching 'name' or name_filter if defined
    :param module:
    :param connection:
    :return:
    """
    buckets = []
    filtered_buckets = []
    final_buckets = []
    # Get all buckets
    try:
        buckets = camel_dict_to_snake_dict(connection.list_buckets())['buckets']
    except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg="Failed to list buckets")

    # Filter buckets if requested
    if name_filter:
        for bucket in buckets:
            if name_filter in bucket['name']:
                filtered_buckets.append(bucket)
    elif name:
        for bucket in buckets:
            if name == bucket['name']:
                filtered_buckets.append(bucket)

    # Return proper list (filtered or all)
    if name or name_filter:
        final_buckets = filtered_buckets
    else:
        final_buckets = buckets
    return(final_buckets)


def get_buckets_facts(connection, buckets, requested_facts, transform_location):
    """
    Retrive additional information about S3 buckets
    """
    full_bucket_list = []
    # Iterate over all buckets and append retrived facts to bucket
    for bucket in buckets:
        bucket.update(get_bucket_details(connection, bucket['name'], requested_facts, transform_location))
        full_bucket_list.append(bucket)

    return(full_bucket_list)


def get_bucket_details(connection, name, requested_facts, transform_location):
    """
    Execute all enabled S3API get calls for selected bucket
    """
    all_facts = {}

    for key in requested_facts:
        if requested_facts[key]:
            if key == 'bucket_location':
                all_facts[key] = {}
                try:
                    all_facts[key] = get_bucket_location(name, connection, transform_location)
                # we just pass on error - error means that resources is undefined
                except botocore.exceptions.ClientError:
                    pass
            else:
                all_facts[key] = {}
                try:
                    all_facts[key] = get_bucket_property(name, connection, key)
                # we just pass on error - error means that resources is undefined
                except botocore.exceptions.ClientError:
                    pass

    return(all_facts)

@AWSRetry.exponential_backoff(max_delay=120, catch_extra_error_codes=['NoSuchBucket', 'OperationAborted'])
def get_bucket_location(name, connection, transform_location=False):
    """
    Get bucket location and optionally transform 'null' to 'us-east-1'
    """
    data = connection.get_bucket_location(Bucket=name)

    # Replace 'null' with 'us-east-1'?
    if transform_location:
        try:
            if not data['LocationConstraint']:
                data['LocationConstraint'] = 'us-east-1'
        except KeyError:
            pass
    # Strip response metadata (not needed)
    try:
        data.pop('ResponseMetadata')
        return(data)
    except KeyError:
        return(data)

@AWSRetry.exponential_backoff(max_delay=120, catch_extra_error_codes=['NoSuchBucket', 'OperationAborted'])
def get_bucket_property(name, connection, get_api_name):
    """
    Get bucket property
    """
    api_call = "get_" + get_api_name
    api_function = getattr(connection, api_call)
    data = api_function(Bucket=name)

    # Strip response metadata (not needed)
    try:
        data.pop('ResponseMetadata')
        return(data)
    except KeyError:
        return(data)


def main():
    """
    Get list of S3 buckets
    :return:
    """
    argument_spec = dict(
        name=dict(type=str, default=""),
        name_filter=dict(type=str, default=""),
        bucket_facts=dict(type='dict', options=dict(
            bucket_accelerate_configuration=dict(type=bool, default=False),
            bucket_acl=dict(type=bool, default=False),
            bucket_cors=dict(type=bool, default=False),
            bucket_encryption=dict(type=bool, default=False),
            bucket_lifecycle_configuration=dict(type=bool, default=False),
            bucket_notification_configuration=dict(type=bool, default=False),
            bucket_location=dict(type=bool, default=False),
            bucket_logging=dict(type=bool, default=False),
            bucket_ownership_controls=dict(type=bool, default=False),
            bucket_policy=dict(type=bool, default=False),
            bucket_policy_status=dict(type=bool, default=False),
            bucket_replication=dict(type=bool, default=False),
            bucket_request_payment=dict(type=bool, default=False),
            bucket_tagging=dict(type=bool, default=False),
            bucket_website=dict(type=bool, default=False),
            public_access_block=dict(type=bool, default=False),
            )),
        transform_location=dict(type='bool', default=False)
    )

    # Ensure we have an empty dict
    result = {}

    # Define mutually exclusive options
    mutually_exclusive = [
        ['name', 'name_filter']
    ]

    # Including ec2 argument spec
    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True, mutually_exclusive=mutually_exclusive)
    is_old_facts = module._name == 'aws_s3_bucket_facts'
    if is_old_facts:
        module.deprecate("The 'aws_s3_bucket_facts' module has been renamed to 'aws_s3_bucket_info', "
                         "and the renamed one no longer returns ansible_facts", date='2021-12-01', collection_name='community.aws')

    # Get parameters
    name = module.params.get("name")
    name_filter = module.params.get("name_filter")
    requested_facts = module.params.get("bucket_facts")
    transform_location = module.params.get("bucket_facts")

    # Set up connection
    connection = {}
    try:
        connection = module.client('s3')
    except (connection.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg='Failed to connect to AWS')

    # Get basic bucket list (name + creation date)
    bucket_list = get_bucket_list(module, connection, name, name_filter)

    # Add information about name/name_filter to result
    if name:
        result['bucket_name'] = name
    elif name_filter:
        result['bucket_name_filter'] = name_filter

    # Gather detailed information about buckets if requested
    bucket_facts = module.params.get("bucket_facts")
    if bucket_facts:
        result['buckets'] = get_buckets_facts(connection, bucket_list, requested_facts, transform_location)
    else:
        result['buckets'] = bucket_list

    # Send exit
    if is_old_facts:
        module.exit_json(msg="Retrieved s3 facts.", ansible_facts=result)
    else:
        module.exit_json(msg="Retrieved s3 info.", **result)

## MAIN ##
if __name__ == '__main__':
    main()
