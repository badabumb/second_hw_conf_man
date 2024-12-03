import os
import toml
import zlib

def load_config(config_file='config.toml'):
    """
    Функция для загрузки конфигурации из файла.
    """
    with open(config_file, 'r') as f:
        return toml.load(f)

def main():
    config = load_config()
def parse_object(object_hash, description=None):
    """
    Извлечь информацию из git-объекта по его хэшу.
    Каждый объект после разжатия выглядит так:
    ┌────────────────────────────────────────────────────────┐
    │ {тип объекта} {размер объекта}\x00{содержимое объекта} │
    └────────────────────────────────────────────────────────┘
    Содержимое объекта имеет разную структуру в зависимости от типа
    """

    # Полный путь к объекту по его хэшу
    object_path = os.path.join(config['repo_path'], '.git', 'objects', object_hash[:2], object_hash[2:])

    # Открываем git-объект
    with open(object_path, 'rb') as file:
        # Разжали объект, получили его сырое содержимое
        raw_object_content = zlib.decompress(file.read())
        # Разделили содержимое объекта на заголовок и основную часть
        header, raw_object_body = raw_object_content.split(b'\x00', maxsplit=1)
        # Извлекли из заголовка информацию о типе объекта и его размере
        object_type, content_size = header.decode().split(' ')

        # Словарь с данными git-объекта:
        # {
        #   'label': текстовая метка, которая будет отображаться на графе
        #   'children': список из детей этого узла (зависимых объектов)
        # }
        object_dict = {}

        # В зависимости от типа объекта используем разные функции для его разбора
        if object_type == 'commit':
            object_dict['label'] = r'[commit]\n' + object_hash[:6]
            object_dict['children'] = parse_commit(raw_object_body)

        elif object_type == 'tree':
            object_dict['label'] = r'[tree]\n' + object_hash[:6]
            object_dict['children'] = parse_tree(raw_object_body)

        elif object_type == 'blob':
            object_dict['label'] = r'[blob]\n' + object_hash[:6]
            object_dict['children'] = []

        # Добавляем дополнительную информацию, если она была
        if description is not None:
            object_dict['label'] += r'\n' + description

        return object_dict


def parse_tree(raw_content):
    """
    Парсим git-объект дерева, который состоит из следующих строк:
    ┌─────────────────────────────────────────────────────────────────┐
    │ {режим} {имя объекта}\x00{хэш объекта в байтовом представлении} │
    │ {режим} {имя объекта}\x00{хэш объекта в байтовом представлении} │
    │ ...                                                             │
    │ {режим} {имя объекта}\x00{хэш объекта в байтовом представлении} │
    └─────────────────────────────────────────────────────────────────┘
    """

    # Дети дерева (соответствующие строкам объекта)
    children = []

    # Парсим данные, последовательно извлекая информацию из каждой строки
    rest = raw_content
    while rest:
        # Извлечение режима
        mode, rest = rest.split(b' ', maxsplit=1)
        # Извлечение имени объекта
        name, rest = rest.split(b'\x00', maxsplit=1)
        # Извлечение хэша объекта и его преобразование в 16ричный формат
        sha1, rest = rest[:20].hex(), rest[20:]
        # Добавляем потомка к списку детей
        children.append(parse_object(sha1, description=name.decode()))

    return children


def parse_commit(raw_content):
    """
    Парсим git-объект коммита, который состоит из следующих строк:
    ┌────────────────────────────────────────────────────────────────┐
    │ tree {хэш объекта дерева в 16ричном представлении}\n           │
    │ parent {хэш объекта коммита в 16ричном представлении}\n        │─╮
    │ parent {хэш объекта коммита в 16ричном представлении}\n        │ │
    │ ...                                                            │ ├─ родителей может быть 0 или несколько
    │ parent {хэш объекта коммита в 16ричном представлении}\n        │─╯
    │ author {имя} <{почта}> {дата в секундах} {временная зона}\n    │
    │ committer {имя} <{почта}> {дата в секундах} {временная зона}\n │
    │ \n                                                             │
    │ {сообщение коммита}                                            │
    └────────────────────────────────────────────────────────────────┘
    """

    # Переводим raw_content в кодировку UTF-8 (до этого он был последовательностью байтов)
    content = raw_content.decode()
    # Делим контент на строки
    content_lines = content.split('\n')

    # Словарь с содержимым коммита
    commit_data = {}

    # Извлекаем хэш объекта дерева, привязанного к коммиту
    commit_data['tree'] = content_lines[0].split()[1]
    content_lines = content_lines[1:]

    # Список родительских коммитов
    commit_data['parents'] = []
    # Парсим всех родителей, сколько бы их ни было
    while content_lines[0].startswith('parent'):
        commit_data['parents'].append(content_lines[0].split()[1])
        content_lines = content_lines[1:]

    # Извлекаем информацию об авторе и коммитере
    while content_lines[0].strip():
        key, *values = content_lines[0].split()
        commit_data[key] = ' '.join(values)
        content_lines = content_lines[1:]

    # Извлекаем сообщение к комиту
    commit_data['message'] = '\n'.join(content_lines[1:]).strip()

    # Возвращаем все зависимости объекта коммита (то есть его дерево и всех родителей)
    return [parse_object(commit_data['tree'])] + \
        [parse_object(parent) for parent in commit_data['parents']]


def get_last_commit():
    """Получить хэш для последнего коммита в ветке"""
    head_path = os.path.join(config['repo_path'], '.git', 'refs', 'heads', config['branch'])
    with open(head_path, 'r') as file:
        return file.read().strip()


def generate_plantuml(filename):
    """
    Создать PlantUML-файл для графа зависимостей.
    """

    def recursive_write(tree, result):
        """
        Рекурсивно перебрать все узлы дерева для построения связей графа.
        """
        label = tree['label']
        for child in tree['children']:
            # Учитываем только уникальные связи
            result.append(f'"{label}" --> "{child["label"]}"')
            recursive_write(child, result)

    # Получаем последний коммит в основной ветке
    last_commit = get_last_commit()

    # Строим дерево зависимостей
    tree = parse_object(last_commit)

    # Формируем данные для PlantUML
    plantuml_result = [
        "@startuml",  # Начало описания PlantUML
        "skinparam defaultFontName Courier"  # Настройка шрифта для читаемости
    ]

    # Рекурсивно добавляем связи в граф
    recursive_write(tree, plantuml_result)

    # Завершаем описание графа
    plantuml_result.append("@enduml")

    # Записываем результат в файл
    with open(filename, 'w') as file:
        file.write("\n".join(plantuml_result))


# Загрузка конфигурации из файла config.toml
with open('config.toml', 'r') as f:
    config = toml.load(f)

# Генерируем файл с PlantUML-нотацией графа зависимостей
generate_plantuml('graph.puml')

if __name__ == "__main__":
    main()