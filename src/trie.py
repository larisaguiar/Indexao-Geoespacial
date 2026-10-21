#Algorithm Radix Tree
class RadixNode:
    def __init__(self, prefix: str = "", is_end: bool = False):
        self.prefix = prefix
        self.children: dict[str, RadixNode] = {}
        self.is_end = is_end


class RadixTree:
    def __init__(self):
        self.root = RadixNode()

    def insert(self, word: str) -> None:
        #Insere uma palavra, dividindo arestas quando tem prefixos comum
        if not word:
            self.root.is_end = True
            return

        node = self.root
        remaining = word
        while remaining:
            child = node.children.get(remaining[0])
            if child is None:
                node.children[remaining[0]] = RadixNode(remaining, is_end=True)
                return

            common_length = 0
            while (
                common_length < len(remaining)
                and common_length < len(child.prefix)
                and remaining[common_length] == child.prefix[common_length]
            ):
                common_length += 1

            if common_length == len(child.prefix):
                remaining = remaining[common_length:]
                node = child
                if not remaining:
                    node.is_end = True
                continue

            old_suffix = child.prefix[common_length:]
            old_branch = RadixNode(old_suffix, is_end=child.is_end)
            old_branch.children = child.children

            child.prefix = child.prefix[:common_length]
            child.is_end = False
            child.children = {old_suffix[0]: old_branch}

            new_suffix = remaining[common_length:]
            if new_suffix:
                child.children[new_suffix[0]] = RadixNode(new_suffix, is_end=True)
            else:
                child.is_end = True
            return

    def search(self, word: str) -> bool:
        #Verifica se a palavra completa existe
        node = self.root
        remaining = word
        while remaining:
            child = node.children.get(remaining[0])
            if child is None or not remaining.startswith(child.prefix):
                return False
            remaining = remaining[len(child.prefix):]
            node = child
        return node.is_end

    #palavra que começa com o prefixo
    def starts_with(self, prefix: str) -> bool:
        if not prefix:
            return True

        node = self.root
        remaining = prefix
        while remaining:
            child = node.children.get(remaining[0])
            if child is None:
                return False

            common_length = 0
            while (
                common_length < len(remaining)
                and common_length < len(child.prefix)
                and remaining[common_length] == child.prefix[common_length]
            ):
                common_length += 1

            if common_length == len(remaining):
                return True
            if common_length < len(child.prefix):
                return False

            remaining = remaining[common_length:]
            node = child
        return True
#retorna uma lista de palavras que começa com o prefixo
    def search_by_prefix(self, prefix: str) -> list[str]:
        node = self.root
        remaining = prefix
        built = ""
        while remaining:
            child = node.children.get(remaining[0])
            if child is None:
                return []

            common_length = 0
            while (
                common_length < len(remaining)
                and common_length < len(child.prefix)
                and remaining[common_length] == child.prefix[common_length]
            ):
                common_length += 1

            if common_length < min(len(remaining), len(child.prefix)):
                return []
            built += child.prefix
            if common_length == len(remaining):
                node = child
                break

            remaining = remaining[common_length:]
            node = child

        words: list[str] = []

        def collect(current: RadixNode, built: str) -> None:
            if current.is_end:
                words.append(built)
            for child in current.children.values():
                collect(child, built + child.prefix)

        collect(node, built)
        return words

#teste - printa arvore
    def print_tree(self) -> None:
        print("Root")

        def print_node(node: RadixNode, indent: str = "") -> None:
            for child in sorted(node.children.values(), key=lambda item: item.prefix):
                status = " (end)" if child.is_end else ""
                print(f"{indent}├── [{child.prefix}]{status}")
                print_node(child, indent + "│   ")

        print_node(self.root)


CompactTrie = RadixTree


if __name__ == "__main__":
    keys = ["deck", "did", "doe", "dog", "doge", "dogs"]
    tree = RadixTree()
    for key in keys:
        tree.insert(key)

    tree.print_tree()
    print("Busca 'dog':", tree.search("dog"))
    print("Busca 'do':", tree.search("do"))
    print("Prefixo 'do':", tree.search_by_prefix("do"))
