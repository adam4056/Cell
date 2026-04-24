import queue

_queue: "queue.Queue[str]" = queue.Queue()


def post(message: str) -> None:
    if message is None:
        return
    text = str(message).rstrip()
    if text:
        _queue.put(text)


def drain() -> list:
    items = []
    while True:
        try:
            items.append(_queue.get_nowait())
        except queue.Empty:
            break
    return items


def has_pending() -> bool:
    return not _queue.empty()
