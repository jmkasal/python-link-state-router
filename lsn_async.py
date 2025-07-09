import asyncio
import json
import random
from link_state_database import LinkStatePacket, LinkStateDatabase, Link


class LinkStateNode:

    def __init__(self, id: int):
        self.id = id
        self.direct_connection = {}
        self.direct_links = {}
        self.lsdb = LinkStateDatabase()
        self.processed_lsas = set()
        self.on = False
        self.server = None

    async def turn_on(self):
        self.on = True
        self.server = await asyncio.start_server(
            self.accept_connections, "localhost", self.id
        )
        asyncio.create_task(self.send_lsa_periodically(30))
        asyncio.create_task(self.send_hello_periodically(15))  # Schedule hello messages

    async def accept_connections(self, reader, writer):
        addr = writer.get_extra_info("peername")
        print(f"Connection from {addr}")

        while self.on:
            try:
                data = await reader.readuntil(b"\r\n")
            except (OSError, ConnectionResetError, EOFError) as e:
                print(f"Connection from {addr} closed")
                keys_to_delete = []
                for key, conn in self.direct_connection.items():
                    if conn == writer:
                        print(f"Setting link from link-id: {self.id}:{key} to infinity")
                        keys_to_delete.append(key)
                        self.direct_links[key] = [key, -1]
                        await self.lsdb.remove(key)
                        new_lsa = await self.lsdb.get(self.id)
                        if new_lsa is None:
                            print(f"No LSA found for {self.id}, skipping for now")
                            break
                        new_lsa.links = [
                            link for link in new_lsa.links if link.link_id != key
                        ]
                        new_lsa.sequence_number += 1
                        await self.forward_lsa(
                            {
                                "type": "lsa",
                                "id": self.id,
                                "lsas": [new_lsa.to_dict()],
                            },
                            writer=writer,
                        )
                for key in keys_to_delete:
                    self.direct_connection.pop(key)
                break
            message = json.loads(data.decode())
            await self.handle_message(message, writer)

    async def handle_message(self, message, writer):
        if message["type"] == "hello":
            # print(f"Message: {message}")
            # await self.send_hello()  # Acknowledge hello by sending another hello
            if (
                message["id"] in self.direct_links
                and self.direct_links[message["id"]][1] == -1
            ):
                print(f"Link to {message['id']} has come up again")
                self.direct_connection[message["id"]] = writer
                self.direct_links[message["id"]][1] = message["cost"]
                if self.id < message["id"]:
                    own_lsa = await self.lsdb.get(self.id)
                    if own_lsa is None:
                        print(f"No LSA found for {self.id}, skipping for now")
                    else:
                        own_lsa.links.append((message["id"], message["cost"]))
                        own_lsa.sequence_number += 1
                        await self.lsdb.add(self.id, own_lsa)
                    lsas = await self.lsdb.get_all()
                    writer.write(
                        (
                            json.dumps(
                                {
                                    "type": "resync",
                                    "id": self.id,
                                    "lsas": [
                                        lsa.to_dict()
                                        for lsa in lsas.values()
                                        if lsa.link_state_id != message["id"]
                                    ],
                                }
                            )
                            + "\r\n"
                        ).encode()
                    )
                    await writer.drain()

            if message["id"] not in self.direct_connection:
                self.direct_connection[message["id"]] = writer
                self.direct_links[message["id"]] = [message["id"], message["cost"]]
            elif message["id"] in self.direct_connection:
                self.direct_links[message["id"]][1] = message["cost"]

        elif message["type"] == "lsa":
            await self._handle_lsa(message, writer)

        elif message["type"] == "resync":
            await self._handle_resync(message, writer)

        else:
            print("Invalid message type")

    async def _handle_lsa(self, message, writer):
        for lsa in message["lsas"]:
            state = (lsa["link_state_id"], lsa["sequence_number"])
            if state not in self.processed_lsas:
                self.processed_lsas.add(state)
                item = await self.lsdb.get(lsa["link_state_id"])
                if item is None:
                    await self.lsdb.add(
                        lsa["link_state_id"],
                        LinkStatePacket.from_dict(lsa),
                    )
                    await self.forward_lsa(message, writer=writer)

                else:
                    if lsa["sequence_number"] >= item.sequence_number:
                        await self.lsdb.add(
                            lsa["link_state_id"],
                            LinkStatePacket.from_dict(lsa),
                        )
                        await self.forward_lsa(message, writer=writer)
                    else:
                        print(
                            "LSA sequence number is not greater than the one in the database. "
                            "Forwarding most recent LSA"
                        )
                        new_lsa = await self.lsdb.get(lsa["link_state_id"])
                        await self.forward_lsa(
                            {
                                "type": "lsa",
                                "id": new_lsa.router_id,
                                "lsas": [new_lsa.to_dict()],
                            },
                            send_back=True,
                            writer=writer,
                        )
            else:
                print(
                    f"LSA {lsa['link_state_id']} with sequence number {lsa['sequence_number']} already processed"
                )

    async def _handle_resync(self, message, writer):
        print(f"handling resync on {self.id} with message: {message}")
        print(self.direct_links)
        if self.id > message["id"]:
            lsas = await self.lsdb.get_all()
            writer.write(
                (
                    json.dumps(
                        {
                            "type": "resync",
                            "id": self.id,
                            "lsas": [
                                lsa.to_dict()
                                for lsa in lsas.values()
                                if lsa.link_state_id != message["id"]
                            ],
                        }
                    )
                    + "\r\n"
                ).encode()
            )
            await writer.drain()

        for lsa in message["lsas"]:
            cur_lsa = await self.lsdb.get(lsa["link_state_id"])
            if (
                cur_lsa is None
                or lsa.get("sequence_number", 0) > cur_lsa.sequence_number
            ):
                await self.lsdb.add(
                    lsa["link_state_id"], LinkStatePacket.from_dict(lsa)
                )

        await self.send_neighbor_lsa()

    async def turn_off(self):
        self.on = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for key in self.direct_connection:
            self.direct_connection[key].close()
        self.direct_connection.clear()
        self.lsdb = LinkStateDatabase()

    async def add_link(self, node: int, cost: int):
        if not self.on:
            print("Node is off")
            return

        if node not in self.direct_connection and node not in self.direct_links:
            reader, writer = await asyncio.open_connection("localhost", node)
            self.direct_connection[node] = writer
            self.direct_links[node] = [node, cost]
            await self.send_hello()  # Send a hello when adding a link
            asyncio.create_task(self.accept_connections(reader, writer))
        elif node in self.direct_links and self.direct_links[node][0] == -1:
            reader, writer = await asyncio.open_connection("localhost", node)
            asyncio.create_task(self.accept_connections(reader, writer))
            self.direct_connection[node] = writer
            print(f"Link to {node} has come up again")
            self.direct_links[node] = [node, cost]
            await self.send_hello()
            if self.id < node:
                lsas = await self.lsdb.get_all()
                print("current lsdb:", lsas)
                writer.write(
                    (
                        json.dumps(
                            {
                                "type": "resync",
                                "id": self.id,
                                "lsas": [
                                    lsa.to_dict()
                                    for lsa in lsas.values()
                                    if lsa.link_state_id != node
                                ],
                            }
                        )
                        + "\r\n"
                    ).encode()
                )
                await writer.drain()

        else:
            print(f"Link to {node} already exists")

    async def remove_link(self, node: int):
        if not self.on:
            print("Node is off")
            return

        if node in self.direct_connection:
            print(f"Removing link to {node} from {self.id}")
            writer = self.direct_connection.pop(node)
            writer.close()
            await self.lsdb.remove(node)
            self.direct_links.pop(node, None)
            await self.send_hello()

    async def send_hello(self):
        if not self.on:
            print("Node is off")
            return

        for key, val in self.direct_connection.items():
            item = self.direct_links.get(key)
            if item:
                message = {
                    "type": "hello",
                    "id": self.id,
                    "cost": item[1],
                }
                # print(f'sending hello from {self.id}')
                val.write((json.dumps(message) + "\r\n").encode())
                await val.drain()  # Ensure the message is sent

    async def send_neighbor_lsa(
        self,
    ):
        if not self.on:
            print("Node is off")
            return
        links = []
        for key, val in self.direct_connection.items():
            links.append(Link(key, self.direct_links[key][1]))

            # print(f'sending lsa from {self.id} to {key}')
        old_lsa = await self.lsdb.get(self.id)
        if old_lsa is None:
            old_lsa = LinkStatePacket(self.id, 0, self.id, links, 60)
        else:
            old_lsa.links = links
            old_lsa.sequence_number += 1
            old_lsa.ttl = 60
        await self.lsdb.add(old_lsa.link_state_id, old_lsa)

        for neighb_conn in self.direct_connection.values():
            # print(f'sending lsas: {lsas_to_send} from {self.id}')
            neighb_conn.write(
                (
                    json.dumps(
                        {"type": "lsa", "id": self.id, "lsas": [old_lsa.to_dict()]}
                    )
                    + "\r\n"
                ).encode()
            )
            await neighb_conn.drain()

    async def forward_lsa(self, message, writer, send_back=False):
        if not self.on:
            print("Node is off")
            return
        if send_back:
            writer.write((json.dumps(message) + "\r\n").encode())
            await writer.drain()
        else:
            # Forward received LSAs to all directly connected neighbors except the sender
            for neighbor_id, conn in self.direct_connection.items():
                if conn != writer:
                    # print(f'Forwarding LSA:{message} from {message["id"]} to {neighbor_id}')
                    conn.write((json.dumps(message) + "\r\n").encode())
                    await writer.drain()

    async def send_lsa_periodically(self, interval):
        while self.on:
            await self.send_neighbor_lsa()
            await asyncio.sleep(interval + random.randint(-5, 5))

    async def send_hello_periodically(self, interval):
        while self.on:
            await self.send_hello()
            await asyncio.sleep(interval)

    def show_peers(self):
        print(self.direct_connection.keys())


async def main():
    node1 = LinkStateNode(8080)
    await node1.turn_on()
    node2 = LinkStateNode(8081)
    await node2.turn_on()
    await node1.add_link(8081, 1)
    node3 = LinkStateNode(8082)
    node4 = LinkStateNode(8083)
    await node3.turn_on()
    await node4.turn_on()
    await node2.add_link(8082, 5)
    await node2.add_link(8083, 2)
    await node3.add_link(8083, 10)

    await asyncio.sleep(40)
    await node1.remove_link(8081)

    # await asyncio.sleep(5)
    # await node1.turn_off()
    count = 1
    try:
        while True:
            await asyncio.sleep(4)
            print(node3.lsdb)
            count += 1
            if count == 17:
                await node1.add_link(8081, 20)

    except KeyboardInterrupt:
        await node1.turn_off()
        await node2.turn_off()


if __name__ == "__main__":
    asyncio.run(main())
