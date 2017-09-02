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
import reconciletags

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

class ReconcileTagsTest(unittest.TestCase):

    def _gcloudAdd(self, digest, tag):
        return ('gcloud container images add-tag {0} {1} -q --format=json'
                .format(_FULL_REPO+'@sha256:'+digest, _FULL_REPO+':'+tag))

    def setUp(self):
        self.r = reconciletags.TagReconciler()
        self.data = {'projects':
                     [{'base_registry': 'gcr.io',
                       'additional_registries': [],
                       'repository': _REPO,
                       'images': [{'digest': _DIGEST1, 'tag': _TAG1}]}]}

    def test_reconcile_tags(self):
        with mock.patch('reconciletags.logging.debug',
                        return_value=_LIST_RESP) as mock_output:
            self.r.reconcile_tags(self.data, False)

            self.assertIn(((["Tagging {0} with {1}".format(
                _FULL_REPO+'@sha256:'+_DIGEST1, _FULL_REPO+":"+_TAG1)],),
                              {'shell': True}), mock_output.mock_calls)

    def test_dry_run(self):
        with mock.patch('reconciletags.logging.debug', 
                        return_value=_LIST_RESP) as mock_output:

            self.r.reconcile_tags(self.data, True)
            mock_output.assert_any_call("Would have tagged {0} with {1}".format(
                _FULL_REPO+'@sha256:'+_DIGEST1, _FULL_REPO+":"+_TAG1))

            self.assertNotIn(((["Tagging {0} with {1}".format(
                _FULL_REPO+'@sha256:'+_DIGEST1, _FULL_REPO+":"+_TAG1)],),
                              {'shell': True}), mock_output.mock_calls)

    def test_get_existing_tags(self):
        with mock.patch('subprocess.check_output',
                        return_value=_LIST_RESP) as mock_output:
            existing_tags = self.r.get_existing_tags(_FULL_REPO)
            self.assertIn(_TAG1, existing_tags)
            mock_output.assert_called_once_with([_GCLOUD_LIST], shell=True)

    def test_add_tag(self):
        with mock.patch('subprocess.check_output',
                        return_value=_LIST_RESP) as mock_output:
            self.r.add_tags(_FULL_REPO+'@sha256:'+_DIGEST2,
                            _FULL_REPO+':'+_TAG2, False)
            mock_output.assert_called_once_with(
                [self._gcloudAdd(_DIGEST2, _TAG2)], shell=True)


if __name__ == '__main__':
    unittest.main()
