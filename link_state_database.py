import asyncio


class Link:

    def __init__(self, link_id: str, cost: int):
        self.link_id = link_id
        self.cost = cost

    def __str__(self):
        return f"Link(link_id={self.link_id}, cost={self.cost})"

    def __repr__(self):
        return str(self)

    def to_dict(self):
        return {"link_id": self.link_id, "cost": self.cost}


class LinkStatePacket:
    def __init__(
        self,
        router_id: int,
        sequence_number: int,
        link_state_id: int,
        links: [Link],
        ttl: int,
    ):
        self.router_id = router_id
        self.sequence_number = sequence_number
        self.link_state_id = link_state_id
        self.links = links
        self.ttl = ttl

    def __str__(self):
        return (
            f"LinkStatePacket(router_id={self.router_id}, sequence_number={self.sequence_number}, "
            f"link_state_id={self.link_state_id}, links={self.links}, ttl={self.ttl})"
        )

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return (
            self.router_id == other.router_id
            and self.sequence_number == other.sequence_number
            and self.link_state_id == other.link_state_id
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.router_id, self.sequence_number, self.link_state_id))

    def to_dict(self):
        return {
            "router_id": self.router_id,
            "sequence_number": self.sequence_number,
            "link_state_id": self.link_state_id,
            "links": [link.to_dict() for link in self.links],
            "ttl": self.ttl,
        }

    @staticmethod
    def from_dict(data):
        return LinkStatePacket(
            data["router_id"],
            data["sequence_number"],
            data["link_state_id"],
            [Link(link["link_id"], link["cost"]) for link in data["links"]],
            data["ttl"],
        )


class LinkStateDatabase:
    def __init__(self):
        self.database = {}
        self.database_lock = asyncio.Lock()
        asyncio.create_task(self.handle_decrement())

    async def add(self, link_id, link_state_packet: LinkStatePacket):
        async with self.database_lock:
            self.database[link_id] = link_state_packet

    async def get(self, link_id) -> LinkStatePacket:
        async with self.database_lock:
            return self.database.get(link_id)

    async def remove(self, link_id):
        async with self.database_lock:
            self.database.pop(link_id, None)

    async def get_all(self):
        async with self.database_lock:
            return self.database.copy()

    async def handle_decrement(self):
        while True:
            await asyncio.sleep(1)
            async with self.database_lock:
                keys_to_delete = []
                for key in list(self.database.keys()):
                    if self.database[key].ttl == 0:
                        keys_to_delete.append(key)
                    else:
                        self.database[key].ttl -= 1
                for key in keys_to_delete:
                    self.database.pop(key, None)

    def __str__(self):
        return str(self.database)
