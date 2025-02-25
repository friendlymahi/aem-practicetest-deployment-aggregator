import subprocess
from lxml import etree
import re
import os
import tempfile
import requests

POM_FILE = 'all/pom.xml'

def evaluate_property(property_name):
    result = subprocess.run(
        ['mvn', 'help:evaluate', f'-Dexpression={property_name}', '-q', '-DforceStdout', f'-f{POM_FILE}'],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def evaluate_string_with_properties(input_string):
    pattern = re.compile(r'\$\{([^}]+)\}')
    while True:
        match = pattern.search(input_string)
        if not match:
            break
        property_name = match.group(1)
        property_value = evaluate_property(property_name)
        input_string = input_string.replace(f'${{{property_name}}}', property_value, 1)
    return input_string

def parse_pom():
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(POM_FILE, parser)
    root = tree.getroot()
    namespaces = {'mvn': 'http://maven.apache.org/POM/4.0.0'}
    etree.register_namespace('mvn', 'http://maven.apache.org/POM/4.0.0')
    print(f"Parsing POM file: {POM_FILE} Base dir is {evaluate_property('project.basedir')}")

    properties = {}
    for prop in root.xpath('./mvn:properties/*', namespaces=namespaces):
        properties[prop.tag.split('}')[1]] = prop.text

    artifacts = []
    fs_artifacts = properties.get('filesystem-artifacts', '').replace('\n', '').strip()
    # Process existing filesystem-artifacts
    for artifact_str in fs_artifacts.split(';'):
        if artifact_str:
            artifact_data = {}
            print(f"Processing artifact", {artifact_str})
            artifact_str = artifact_str.replace('artifact:', '')
            for part in artifact_str.split(','):
                key, value = part.split('=')
                artifact_data[key] = value
            artifacts.append(artifact_data)

    # Process dependencies with scope system
    dependencies_to_remove = []
    for dependency in root.xpath('.//mvn:dependency', namespaces=namespaces):
        scope = dependency.find('mvn:scope', namespaces)
        system_path = dependency.find('mvn:systemPath', namespaces)
        if scope is not None and scope.text == 'system' and system_path is not None:
            artifact_data = {
                'groupId': dependency.find('mvn:groupId', namespaces).text,
                'artifactId': dependency.find('mvn:artifactId', namespaces).text,
                'version': dependency.find('mvn:version', namespaces).text,
                'type': dependency.find('mvn:type', namespaces).text,
                'systemPath': system_path.text
            }
            # Add to artifacts if not already present
            if artifact_data not in artifacts:
                artifacts.append(artifact_data)
            dependencies_to_remove.append((dependency, scope, system_path))

    return artifacts, dependencies_to_remove, tree, root

def download_file(url, dest_path):
    response = requests.get(url)
    response.raise_for_status()
    with open(dest_path, 'wb') as file:
        file.write(response.content)

def install_artifacts(artifacts):
    for artifact in artifacts:
        evaluated_system_path = evaluate_string_with_properties(artifact["systemPath"])
        if evaluated_system_path.startswith('http://') or evaluated_system_path.startswith('https://'):
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                download_file(evaluated_system_path, temp_file.name)
                evaluated_system_path = temp_file.name
        subprocess.run([
            'mvn', 'install:install-file',
            f'-DgroupId={artifact["groupId"]}',
            f'-DartifactId={artifact["artifactId"]}',
            f'-Dversion={artifact["version"]}',
            f'-Dpackaging={artifact["type"]}',
            f'-Dfile={evaluated_system_path}',
            f'-DgeneratePom=true',
        ], check=True)

def update_pom(tree, root, dependencies_to_remove, artifacts):
    namespaces = {'mvn': 'http://maven.apache.org/POM/4.0.0'}
    properties = root.find('./mvn:properties', namespaces)
    fs_artifacts = ';'.join(
        [f"\nartifact:groupId={a['groupId']},artifactId={a['artifactId']},version={a['version']},type={a['type']},systemPath={a['systemPath']}" for a in artifacts]
    )
    print(f"Updating filesystem-artifacts property: {fs_artifacts}")
    print("All properties:")
    for key, value in properties.items():
        print(f"{key}: {value}")
    # Update filesystem-artifacts property
    fs_artifacts_element = properties.find('mvn:filesystem-artifacts', namespaces)
    if fs_artifacts_element is not None:
        fs_artifacts_element.text = fs_artifacts
    else:
        raise RuntimeError("'filesystem-artifacts' element not found in POM properties.")

    for dependency, scope, system_path in dependencies_to_remove:
        dependency.remove(scope)
        dependency.remove(system_path)

    tree.write(POM_FILE, pretty_print=True, xml_declaration=True, encoding='UTF-8')

if __name__ == '__main__':
    try:
        artifacts, dependencies_to_remove, tree, root = parse_pom()
        install_artifacts(artifacts)
        update_pom(tree, root, dependencies_to_remove, artifacts)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred: {e}")
        print("Retaining original properties for rerun.")