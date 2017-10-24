# Copyright 2017 Google Inc. All rights reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reads json files mapping docker digests to tags and reconciles them.

Reads all json files in current directory and parses it into repositories
and tags. Calls gcloud container images add-tag on each entry.
If there are no changes that api call is no-op.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import glob
import unittest
from containerregistry.client import docker_creds
from containerregistry.client import docker_name
from containerregistry.client.v2_2 import docker_image
from containerregistry.client.v2_2 import docker_session
from containerregistry.transport import transport_pool
from containerregistry.tools import patched
import httplib2


class TagReconciler:

    def add_tags(self, digest, tag, dry_run):
        if dry_run:
            logging.debug('Would have tagged {0} with {1}'.format(digest, tag))
            return

        src_name = docker_name.Digest(digest)
        dest_name = docker_name.Tag(tag)
        creds = docker_creds.DefaultKeychain.Resolve(src_name)
        transport = transport_pool.Http(httplib2.Http)

        with docker_image.FromRegistry(src_name, creds, transport) as src_img:
            if src_img.exists():
                creds = docker_creds.DefaultKeychain.Resolve(dest_name)
                logging.debug('Tagging {0} with {1}'.format(digest, tag))
                with docker_session.Push(dest_name, creds, transport) as push:
                        push.upload(src_img)
            else:
                logging.debug("""Unable to tag {0}
                    as the image can't be found""".format(digest))

    def get_existing_tags(self, full_repo, digest):
        full_digest = full_repo + '@sha256:' + digest
        existing_tags = []

        name = docker_name.Digest(full_digest)
        creds = docker_creds.DefaultKeychain.Resolve(name)
        transport = transport_pool.Http(httplib2.Http)

        with docker_image.FromRegistry(name, creds, transport) as img:
            if img.exists():
                existing_tags = img.tags()
            else:
                logging.debug(
                    """Unable to get existing tags for {0}
                        as the image can't be found""".format(full_digest))
        return existing_tags

    def get_tagged_digest(self, manifests, tag):
        for digest in manifests:
            if tag in manifests[digest]['tag']:
                return digest
        return ''

    def get_digest_from_prefix(self, repo, prefix):
        name = docker_name.Repository(repo)
        creds = docker_creds.DefaultKeychain.Resolve(name)
        transport = transport_pool.Http(httplib2.Http)

        with docker_image.FromRegistry(name, creds, transport) as img:
            digests = [d[len('sha256:'):] for d in img.manifests()]
            matches = [d for d in digests if d.startswith(prefix)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) == 0:
                raise AssertionError('{0} is not a valid prefix'.format(
                                                                 prefix))
        raise AssertionError('{0} is not a unique digest prefix'.format(
                                                                 prefix))

    def reconcile_tags(self, data, dry_run):
        for project in data['projects']:

            default_registry = project['base_registry']
            registries = project.get('additional_registries', [])
            registries.append(default_registry)

            default_repo = os.path.join(default_registry,
                                        project['repository'])

            for image in project['images']:
                digest = self.get_digest_from_prefix(default_repo,
                                                     image['digest'])

                default_digest = default_repo + '@sha256:' + digest
                default_name = docker_name.Digest(default_digest)
                default_creds = (docker_creds.DefaultKeychain
                                 .Resolve(default_name))
                transport = transport_pool.Http(httplib2.Http)

                # Bail out if the digest in the config file doesn't exist.
                with docker_image.FromRegistry(default_name,
                                               default_creds,
                                               transport) as img:

                    if not img.exists():
                        logging.debug('Could not retrieve  ' +
                                      '{0}'.format(default_digest))
                        return

                for registry in registries:

                    full_repo = os.path.join(registry, project['repository'])
                    full_digest = full_repo + '@sha256:' + digest
                    name = docker_name.Digest(full_digest)
                    creds = docker_creds.DefaultKeychain.Resolve(name)

                    with docker_image.FromRegistry(name, creds,
                                                   transport) as img:
                        if img.exists():

                            existing_tags = img.tags()
                            logging.debug('Existing Tags: ' +
                                          '{0}'.format(existing_tags))

                            manifests = img.manifests()
                            tagged_digest = self.get_tagged_digest(
                                manifests, image['tag'])

                            # Don't retag an image if the tag already exists
                            if tagged_digest.startswith('sha256:'):
                                tagged_digest = tagged_digest[len('sha256:'):]
                            if tagged_digest.startswith(digest):
                                logging.debug('Skipping tagging %s with %s as '
                                              'that tag already exists.',
                                              digest, image['tag'])
                                continue

                        # We can safely retag now.
                        full_tag = full_repo + ':' + image['tag']
                        self.add_tags(default_digest, full_tag, dry_run)

                logging.debug(self.get_existing_tags(default_repo, digest))


def create_temp_dir(files):
    config_dir = "../config/"
    os.mkdir(config_dir)
    tag_dir = config_dir + "tag"
    os.mkdir(tag_dir)

    for file in files:
        if os.path.isfile(file):
            shutil.copy(file, tag_dir)
        else:
            raise AssertionError("{0} is not a valid file".format(file))

def delete_temp_dir():
    config_dir = "../config/"
    shutil.rmtree(config_dir)

def run_config_integrity_test(files):
    create_temp_dir(files)
    if os.path.isfile('config_integrity.par'):
        print('exists')
    subprocess.check_call(['reconciletags/config_integrity.par'])

def run_data_integrity_test(files):
    create_temp_dir(files)
    subprocess.check_call(['reconciletags/data_integrity.par'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', dest='dry_run',
                        help='Runs tests to make sure input files are valid, and runs a dry run of the reconciler',
                        action='store_true', default=False)
    parser.add_argument('files',
                        help='The files to run the reconciler on',
                        nargs='+')
    parser.add_argument('--data-integrity', dest='data_integrity',
                        help='Runs a test to make sure the data in the input files is the same as in prod',
                        action='store_true', default=False)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)

    if args.data_integrity:
        try:
            run_data_integrity_test(args.files)
        finally:
            delete_temp_dir() 
        return

    if args.dry_run:
        try:
            run_config_integrity_test(args.files)
        finally:
            delete_temp_dir() 

    r = TagReconciler()
    for f in args.files:
        logging.debug('---Processing {0}---'.format(f))
        with open(f) as tag_map:
            data = json.load(tag_map)
            r.reconcile_tags(data, args.dry_run)


if __name__ == '__main__':
    with patched.Httplib2():
        main()
