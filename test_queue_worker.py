import unittest
from unittest.mock import patch

import queue_worker


class QueueWorkerTest(unittest.TestCase):
    def test_successful_jobs_are_acknowledged(self) -> None:
        messages = [
            {"message_id": "msg-1", "payload": {"listing": "lamp"}},
            {"message_id": "msg-2", "payload": {"listing": "desk"}},
        ]

        with (
            patch("queue_worker.infrai.queue.consume", return_value={"items": messages}),
            patch("queue_worker.infrai.queue.ack") as ack,
            patch.object(queue_worker.StartRateLimiter, "wait"),
        ):
            completed = queue_worker.run_batch(
                concurrency=2,
                per_second=10,
                handler=lambda payload: None,
            )

        self.assertCountEqual(completed, ["msg-1", "msg-2"])
        self.assertEqual({call.kwargs["message_id"] for call in ack.call_args_list}, {"msg-1", "msg-2"})


if __name__ == "__main__":
    unittest.main()
