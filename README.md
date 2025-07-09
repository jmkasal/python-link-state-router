# Async Routing Protocol

## Overview

This project implements an asynchronous routing protocol using Python. It includes components for managing link state databases, handling link state advertisements (LSAs), and simulating network nodes that communicate asynchronously.

## Features

- **Link State Database**: Stores and manages link state packets with support for asynchronous operations.
- **Link State Node**: Simulates a network node that can send and receive LSAs, manage direct connections, and periodically send hello and LSA messages.
- **Asynchronous Communication**: Utilizes Python's `asyncio` for non-blocking operations and efficient handling of network events.

## Folder Structure

- `lsn_async.py`: Contains the implementation of the `LinkStateNode` class, which simulates a network node.
- `link_state_database.py`: Implements the `LinkStateDatabase` class for managing link state packets and their TTLs.
- `ip_prefix_trie.py`: Provides a prefix trie implementation for efficient IP prefix matching and manipulation. (Will be used in later version of project)

## Requirements

- Python 3.8 or higher
- Libraries: `asyncio`, `json`, `random`

## Usage

1. Run the `lsn_async.py` file to simulate network nodes and their interactions.
2. Use the `LinkStateNode` class to create nodes, establish links, and manage routing information.
3. Customize the simulation parameters in the `main()` function of `lsn_async.py`.

## Example

```python
async def main():
    node1 = LinkStateNode(8080)
    await node1.turn_on()
    node2 = LinkStateNode(8081)
    await node2.turn_on()
    await node1.add_link(8081, 1)
    # Add more nodes and links as needed
```
