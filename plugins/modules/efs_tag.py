#!/usr/bin/python
"""
Copyright: (c) 2021, Milan Zink <zeten30@gmail.com>
GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = r'''
---
module: efs_tag
version_added: 1.6.0
short_description: create and remove tags on Amazon EFS resources
notes:
    - none
description:
    - Creates and removes tags for Amazon EFS resources.
    - Resources are referenced by their ID (filesystem or filesystem access point)
author:
  - Milan Zink (@zeten30)
requirements: [ boto3, botocore ]
options:
  resource:
    description:
      - EFS Filesystem ID or EFS Filesystem Access Point ID
    type: str
  state:
    description:
      - Whether the tags should be present or absent on the resource.
    default: present
    choices: ['present', 'absent']
    type: str
  tags:
    description:
      - A dictionary of tags to add or remove from the resource.
      - If the value provided for a tag is null and I(state=absent), the tag will be removed regardless of its current value.
    type: dict
  purge_tags:
    description:
      - Whether unspecified tags should be removed from the resource.
      - Note that when combined with I(state=absent), specified tags with non-matching values are not purged.
    type: bool
    default: false
extends_documentation_fragment:
- amazon.aws.aws
- amazon.aws.ec2

'''

EXAMPLES = r'''
- name: Ensure tags are present on a resource
  community.aws.efs_tag:
    resource: fs-123456ab
    state: present
    tags:
      Name: MyEFS
      Env: Production

- name: Remove the Env tag
  community.aws.efs_tag:
    resource: fs-123456ab
    state: present
    tags:
      Name: MyEFS
      Env: Production
    state: absent

- name: Remove the Env tag if it's currently 'development'
  community.aws.efs_tag:
    resource: fsap-78945ff
    state: absent
    tags:
      Env: development

- name: Remove all tags except for Name
  community.aws.efs_tag:
    resource: fsap-78945ff
    state: absent
    tags:
        Name: foo
    purge_tags: true
'''

RETURN = r'''
tags:
  description: A dict containing the tags on the resource
  returned: always
  type: dict
added_tags:
  description: A dict of tags that were added to the resource
  returned: If tags were added
  type: dict
removed_tags:
  description: A dict of tags that were removed from the resource
  returned: If tags were removed
  type: dict
'''

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    # Handled by AnsibleAWSModule
    pass

from ansible_collections.amazon.aws.plugins.module_utils.core import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.ec2 import boto3_tag_list_to_ansible_dict, ansible_dict_to_boto3_tag_list, compare_aws_tags


def get_tags(efs, module, resource):
    '''
    Get resource tags
    '''
    try:
        return boto3_tag_list_to_ansible_dict(efs.list_tags_for_resource(ResourceId=resource)['Tags'])
    except (BotoCoreError, ClientError) as get_tags_error:
        module.fail_json_aws(get_tags_error, msg='Failed to fetch tags for resource {0}'.format(resource))


def main():
    '''
    MAIN
    '''
    argument_spec = dict(
        resource=dict(required=False),
        tags=dict(type='dict'),
        purge_tags=dict(type='bool', default=False),
        state=dict(default='present', choices=['present', 'absent'])
    )

    required_if = [('state', 'present', ['tags']), ('state', 'absent', ['tags'])]

    module = AnsibleAWSModule(argument_spec=argument_spec, required_if=required_if, supports_check_mode=True)
    resource = module.params['resource']
    tags = module.params['tags']
    state = module.params['state']
    purge_tags = module.params['purge_tags']

    result = {'changed': False}

    efs = module.client('efs')

    current_tags = get_tags(efs, module, resource)

    add_tags, remove = compare_aws_tags(current_tags, tags, purge_tags=purge_tags)

    remove_tags = {}

    if state == 'absent':
        for key in tags:
            if key in current_tags and (tags[key] is None or current_tags[key] == tags[key]):
                remove_tags[key] = current_tags[key]

    for key in remove:
        remove_tags[key] = current_tags[key]

    if remove_tags:
        result['changed'] = True
        result['removed_tags'] = remove_tags
        if not module.check_mode:
            try:
                efs.untag_resource(ResourceId=resource, TagKeys=list(remove_tags.keys()))
            except (BotoCoreError, ClientError) as remove_tag_error:
                module.fail_json_aws(remove_tag_error, msg='Failed to remove tags {0} from resource {1}'.format(remove_tags, resource))

    if state == 'present' and add_tags:
        result['changed'] = True
        result['added_tags'] = add_tags
        current_tags.update(add_tags)
        if not module.check_mode:
            try:
                tags = ansible_dict_to_boto3_tag_list(add_tags)
                efs.tag_resource(ResourceId=resource, Tags=tags)
            except (BotoCoreError, ClientError) as set_tag_error:
                module.fail_json_aws(set_tag_error, msg='Failed to set tags {0} on resource {1}'.format(add_tags, resource))

    result['tags'] = get_tags(efs, module, resource)
    module.exit_json(**result)


if __name__ == '__main__':
    main()
