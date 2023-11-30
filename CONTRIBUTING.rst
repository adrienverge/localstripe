Contributing to localstripe
===========================

We would love you to contribute to localstripe and help make it even better
than it is today!

We maintain localstripe voluntarily, these guidelines goal is to make our
reviews as easy as possible and keep a helpful Git history.

Notifications
-------------

We receive email notifications during conversations but also when you push on
branches of open pull requests. To avoid spamming us please open pull requests
only when you are 90% sure commits, linting and tests are ready. We will help
you with the last 10%.

Describe your changes
---------------------

Please describe your changes (fix or feature) inside the commits messages. The
commit is the key piece in a Git repository to track change over long term. So
each commit should be as complete and as simple as possible.

A pull request can contain multiple commits if you think it's relevant, but
each commit should solve one problem and only one. If one of your commits adds
an issue, that you fix in the next commit of the same pull request, please
squash them.

The Linux kernel is the biggest open-source project of all time, so you can
basically `refer to it`_ on how to commit.

.. _refer to it: https://www.kernel.org/doc/html/v5.14/process/submitting-patches.html#describe-your-changes

Cosmetic code changes
---------------------

We are less than likely to accept them. The main reason is that it makes the
Git history harder to explore.

Lint
----

Before opening a pull request, please run ``flake8`` as `our automated tests
do`_.

.. _our automated tests do: https://github.com/adrienverge/localstripe/blob/e8de08d/.github/workflows/tests.yaml#L23

Tests
-----

Before opening a pull request, please run the test suite. You can use:

.. code:: shell

 find -name '*.py' | entr -r python -m localstripe --from-scratch
 curl -X DELETE localhost:8420/_config/data && ./test.sh
