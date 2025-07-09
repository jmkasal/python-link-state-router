class IpPrefixTrie:
    class Node:
        def __init__(self):
            self.children = {}
            self.prefix_len = None
            self.route_name = None
            self.cidr = None
            self.routes = set()

    def __init__(self):
        self.root = self.Node()

    @staticmethod
    def enumerate_ending_addresses(network, mask):

        # Convert the network address to an integer
        network_parts = network.split('.')
        network_int = sum(int(octet) << (24 - 8 * i) for i, octet in enumerate(network_parts))

        # Calculate the number of addresses in the subnet
        num_addresses = 2 ** (32 - mask)

        # Generate all addresses in the subnet
        for i in range(num_addresses):
            yield network_int + i

    @staticmethod
    def prefix_to_closest_oct(prefix, mask):
        # Convert the prefix to an integer
        prefix_parts = prefix.split('.')
        prefix_int = sum(int(octet) << (24 - 8 * i) for i, octet in enumerate(prefix_parts))

        # Calculate the number of addresses in the subnet
        octet = mask // 8
        if mask % 8 == 0 and mask != 0:
            octet -= 1

        # Generate all addresses in the subnet
        for i in range(4):
            if i == octet:
                # we need to iterate through all prefixes between the start of the mask
                # and the next nearest multiple of 8
                mask_num = (prefix_int >> (24 - 8 * i)) & 0xFF
                parts = []
                for j in range(2 ** ((8 * (octet + 1)) - mask)):
                    # print(f"Octet {i} is the closest octet to the mask")
                    parts.append(mask_num + j)
                yield parts
                break
            else:
                # print(f"Octet {i} is not the closest octet to the mask")
                yield prefix_int >> (24 - 8 * i) & 0xFF

        # return [prefix_int + i for i in range(num_addresses)]

    def insert(self, ip_prefix, route_name=None):
        route = (ip_prefix, route_name)
        parts = ip_prefix.split('/')
        network, mask = parts[0], int(parts[1])
        node = self.root
        for part in self.prefix_to_closest_oct(network, mask):
            if type(part) is not list:
                if part not in node.children:
                    node.children[part] = self.Node()

                node = node.children[part]
            else:
                for prefix in part:
                    if prefix not in node.children:
                        match = self.Node()
                        match.prefix_len = mask
                        match.route_name = route_name
                        node.children[prefix] = match
                        node.children[prefix].cidr = ip_prefix
                        node.children[prefix].routes.add(route)
                    else:
                        node.children[prefix].routes.add(route)
                        if node.children[prefix].prefix_len is None or node.children[prefix].prefix_len < mask:
                            node.children[prefix].prefix_len = mask
                            node.children[prefix].route_name = route_name
                            node.children[prefix].cidr = ip_prefix

    def remove(self, ip_prefix, route_name):
        node = self.root
        parts = ip_prefix.split('/')
        network, mask = parts[0], int(parts[1])
        potential_matches = []
        for part in self.prefix_to_closest_oct(network, mask):
            if type(part) is not list:
                if part not in node.children:
                    return
                node = node.children[part]
                potential_matches.append(node)
            else:
                for prefix in part:
                    if prefix not in node.children:
                        return
                    match = node.children[prefix]
                    match.routes.remove((ip_prefix, route_name))
                    prefix_len = -1
                    for r in match.routes:
                        if r[1] is not None:
                            prefix_len = max(prefix_len, int(r[0].split('/')[1]))
                            match.prefix_len = prefix_len
                            match.route_name = r[1]
                            match.cidr = r[0]

        for match in reversed(potential_matches):
            to_delete = []
            for key, value in match.children.items():
                if not value.routes and not value.children:
                    to_delete.append(key)
            for key in to_delete:
                match.children.pop(key)

    def search(self, ip):
        node = self.root
        for addr in self.enumerate_ending_addresses(ip, 32):
            best_match = -1, None, None
            for i in range(4):
                char = (addr >> (24 - 8 * i)) & 0xFF
                if char not in node.children:
                    break

                node = node.children[char]
                if node.prefix_len is not None and node.prefix_len > best_match[0]:
                    best_match = node.prefix_len, node.cidr, node.route_name,

            if best_match[0] != -1:
                return best_match
        return None
