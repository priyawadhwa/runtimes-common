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

"""Unit tests for reconcile-tags.py.

Unit tests for reconcile-tags.py.
"""
import unittest
import mock
from mock import patch
from interface import implements
import nose
import reconciletags
from containerregistry.client.v2_2 import docker_image
from containerregistry.client.v2_2 import docker_session

_REGISTRY = 'gcr.io'
_REPO = 'foobar/baz'
_FULL_REPO = _REGISTRY + '/' + _REPO
_DIGEST1 = '0000000000000000000000000000000000000000000000000000000000000000'
_DIGEST2 = '0000000000000000000000000000000000000000000000000000000000000001'
_TAG1 = 'tag1'
_TAG2 = 'tag2'

_LIST_RESP = """
[
  {
    "digest": "0000000000000000000000000000000000000000000000000000000000000000",
    "tags": [
      "tag1"
    ],
    "timestamp": {
    }
  }
]
"""

_EXISTING_TAGS = "Existing Tags: {0}".format([_TAG1])

class MockImage(docker_image.DockerImage):

    def __init__(self):
        """Initialize MockImage object"""

    def manifest(self):
        """The JSON manifest referenced by the tag/digest. """

    def config_file(self):
        """The raw blob string of the config file."""

    def blob(self, digest):
        """The raw blob of the layer. """

    def __enter__(self):
        """Open the image for reading."""

    def __exit__(self, unused_type, unused_value, unused_traceback):
        """Close the image."""

class ReconcileTagsTest(unittest.TestCase):

    def setUp(self):
        self.r = reconciletags.TagReconciler()
        self.data = {'projects':
                     [{'base_registry': 'gcr.io',
                       'additional_registries': [],
                       'repository': _REPO,
                       'images': [{'digest': _DIGEST1, 'tag': _TAG1}]}]}


    @patch('containerregistry.client.v2_2.docker_session.Push')
    @patch('containerregistry.client.v2_2.docker_image.FromRegistry')
    def test_reconcile_tags(self, mock_get_image, mock_docker_session):
        mock_get_image.return_value = docker_image.FromRegistry()
        mock_docker_session.return_value = docker_session.Push()

        
        with mock.patch('reconciletags.logging.debug',
                        return_value=_LIST_RESP) as mock_output:

            self.r.reconcile_tags(self.data, False)
            assert mock_get_image.called
            assert mock_docker_session.called
            
            self.assertIn((("Tagging {0} with {1}".format(
                _FULL_REPO+'@sha256:'+_DIGEST1, _FULL_REPO+":"+_TAG1))), mock_output.mock_calls)


if __name__ == '__main__':
    unittest.main()