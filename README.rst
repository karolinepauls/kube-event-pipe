kube-event-pipe
===============

Write deduplicated events to a file as JSON.


Installation
------------

.. code:: sh

    docker pull karolinepauls/kube-event-pipe


How it works
------------

A rotated set of bloom filters is maintained, with all of them read from and only the most recent
one written to. Message name (``.metadata.name``) is used for key identity and is saved and looked
up in the bloom filters. This lets us deduplicate watched events. Since bloom filters are mmapped,
the memory of seen messages persists across restarts.


Configuration
-------------

===================================  =====================================================  =============
Variable                             Description                                            Default value
===================================  =====================================================  =============
KUBE_EVENT_PIPE_DESTINATION          Log file to append events to                           ``-`` (stdout)
KUBE_EVENT_PIPE_LOG_LEVEL            Log level, one of                                      ``INFO``
                                     https://docs.python.org/3/library/logging.html#levels
KUBE_EVENT_PIPE_PERSISTENCE_PATH     Directory to store bloom filters in                    ``.`` (CWD)
KUBE_EVENT_PIPE_FILTER_CAPACITY      Bloom filter capacity                                  ``1_000_000``
KUBE_EVENT_PIPE_FILTER_ERROR_RATE    Bloom filter error rate                                ``0.01``
KUBE_EVENT_PIPE_BATCH_COUNT          Number of rotated bloom filters                        ``3``
KUBE_EVENT_PIPE_BATCH_DURATION_SEC   Time between bloom filter rotations                    ``3600``
===================================  =====================================================  =============


Development
-----------

.. code:: sh

    git clone https://gitlab.com/karolinepauls/kube-event-pipe.git
    cd kube-event-pipe
    # virtualenv ...
    pip install -e .[dev]
