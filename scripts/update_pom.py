#!/usr/bin/env python3

import argparse
from lxml import etree as ET
import os
import requests

def get_default_args():
    return {
        'scope': 'provided',
        'action': 'add/update',
        'targetPath': '/apps/practicemain-packages/install',
        'artifactResolution': 'default',
        'type': 'zip'
    }

def validate_args(args):
    required_fields = ['groupId', 'artifactId', 'version']
    for field in required_fields:
        if not args.get(field):
            raise ValueError(f"Missing required argument: {field}")

def download_artifact(url, groupId, artifactId, version, type, classifier=None):
    classifier_part = f"-{classifier}" if classifier else ""
    output_filename = f"{artifactId}-{version}{classifier_part}.{type}"
    file_path = f"all/lib/{groupId.replace('.', '/')}/{artifactId}/{output_filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    response = requests.get(url)
    response.raise_for_status()
    with open(file_path, 'wb') as file:
        file.write(response.content)

    # Delete existing versions of the artifact with the same artifact ID and type
    for file in os.listdir("all/lib"):
        if file.startswith(artifactId) and file.endswith(f".{type}") and file != output_filename:
            os.remove(os.path.join("all/lib", file))

    return file_path

def update_dependency(dependencies, dependencyArgs, namespaces):
    dependency = None
    for dep in dependencies.findall('pom:dependency', namespaces):
        groupId = dep.find('pom:groupId', namespaces).text
        artifactId = dep.find('pom:artifactId', namespaces).text
        dep_type = dep.find('pom:type', namespaces).text if dep.find('pom:type', namespaces) is not None else 'jar'
        classifier = dep.find('pom:classifier', namespaces)
        classifier_text = classifier.text if classifier is not None else None
        if groupId == dependencyArgs['groupId'] and artifactId == dependencyArgs['artifactId'] and dep_type == dependencyArgs['type'] and classifier_text == dependencyArgs.get('classifier'):
            dependency = dep
            break

    if dependencyArgs['action'] == 'delete' and dependency is not None:
        dependencies.remove(dependency)
        print(f"Removed dependency: {dependencyArgs['groupId']}:{dependencyArgs['artifactId']}")
    else:
        if dependency is None:
            dependency = ET.SubElement(dependencies, '{http://maven.apache.org/POM/4.0.0}dependency')
            ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}groupId').text = dependencyArgs['groupId']
            ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}artifactId').text = dependencyArgs['artifactId']
            ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}type').text = dependencyArgs['type']
            print(f"Added new dependency: {dependencyArgs['groupId']}:{dependencyArgs['artifactId']}")

        version_element = dependency.find('pom:version', namespaces)
        if version_element is None:
            version_element = ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}version')
        version_element.text = dependencyArgs['version']

        classifier_element = dependency.find('pom:classifier', namespaces)
        if 'classifier' in dependencyArgs:
            if classifier_element is None:
                classifier_element = ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}classifier')
            classifier_element.text = dependencyArgs['classifier']
        elif classifier_element is not None:
            dependency.remove(classifier_element)

        if dependencyArgs['artifactResolution'] == 'download':
            scope_element = dependency.find('pom:scope', namespaces)
            if scope_element is None:
                scope_element = ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}scope')
            scope_element.text = 'system'

            system_path_element = dependency.find('pom:systemPath', namespaces)
            if system_path_element is None:
                system_path_element = ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}systemPath')
            classifier_part = f"-{dependencyArgs['classifier']}" if 'classifier' in dependencyArgs else ""
            system_path_element.text = f"${{project.basedir}}/lib/{dependencyArgs['groupId'].replace('.', '/')}/{dependencyArgs['artifactId']}/{dependencyArgs['artifactId']}-{dependencyArgs['version']}{classifier_part}.{dependencyArgs['type']}"
        else:
            scope_element = dependency.find('pom:scope', namespaces)
            if scope_element is None:
                scope_element = ET.SubElement(dependency, '{http://maven.apache.org/POM/4.0.0}scope')
            scope_element.text = dependencyArgs['scope']

        print(f"Updated dependency: {dependencyArgs['groupId']}:{dependencyArgs['artifactId']}")

def update_embeddeds(embeddeds, embeddedArgs, namespaces):
    embedded = None
    for emb in embeddeds.findall('pom:embedded', namespaces):
        groupId = emb.find('pom:groupId', namespaces).text
        artifactId = emb.find('pom:artifactId', namespaces).text
        emb_type = emb.find('pom:type', namespaces).text if emb.find('pom:type', namespaces) is not None else 'jar'
        if groupId == embeddedArgs['groupId'] and artifactId == embeddedArgs['artifactId'] and emb_type == embeddedArgs['type']:
            embedded = emb
            break

    if embeddedArgs['action'] == 'delete' and embedded is not None:
        embeddeds.remove(embedded)
        print(f"Removed embedded: {embeddedArgs['groupId']}:{embeddedArgs['artifactId']}")
    else:
        if embedded is None:
            embedded = ET.SubElement(embeddeds, '{http://maven.apache.org/POM/4.0.0}embedded')
            ET.SubElement(embedded, '{http://maven.apache.org/POM/4.0.0}groupId').text = embeddedArgs['groupId']
            ET.SubElement(embedded, '{http://maven.apache.org/POM/4.0.0}artifactId').text = embeddedArgs['artifactId']
            ET.SubElement(embedded, '{http://maven.apache.org/POM/4.0.0}type').text = embeddedArgs['type']
            print(f"Added new embedded: {embeddedArgs['groupId']}:{embeddedArgs['artifactId']}")

        target_element = embedded.find('pom:target', namespaces)
        if target_element is None:
            target_element = ET.SubElement(embedded, '{http://maven.apache.org/POM/4.0.0}target')
        target_element.text = embeddedArgs['targetPath']
        print(f"Updated embedded: {embeddedArgs['groupId']}:{embeddedArgs['artifactId']}")

def update_pom(artifactArgs):
    default_args = get_default_args()
    for key, value in default_args.items():
        if key not in artifactArgs:
            artifactArgs[key] = value

    if artifactArgs['artifactResolution'] == 'download':
        file_path = download_artifact(artifactArgs['url'], artifactArgs['groupId'], artifactArgs['artifactId'], artifactArgs['version'], artifactArgs['type'], artifactArgs.get('classifier'))
        print(f"Downloaded artifact to {file_path}")

    parser = ET.XMLParser()
    tree = ET.parse('all/pom.xml', parser)
    root = tree.getroot()
    namespaces = {'pom': 'http://maven.apache.org/POM/4.0.0'}
    ET.register_namespace('pom', 'http://maven.apache.org/POM/4.0.0')

    dependencies = root.find('pom:dependencies', namespaces)
    if dependencies is None:
        dependencies = ET.SubElement(root, '{http://maven.apache.org/POM/4.0.0}dependencies')
        print("Created new dependencies element")

    update_dependency(dependencies, artifactArgs, namespaces)

    build = root.find('pom:build', namespaces)
    if build is not None:
        plugins = build.find('pom:plugins', namespaces)
        if plugins is not None:
            for plugin in plugins.findall('pom:plugin', namespaces):
                artifactId = plugin.find('pom:artifactId', namespaces).text
                if artifactId == 'filevault-package-maven-plugin':
                    configuration = plugin.find('pom:configuration', namespaces)
                    if configuration is not None:
                        embeddeds = configuration.find('pom:embeddeds', namespaces)
                        if embeddeds is None:
                            embeddeds = ET.SubElement(configuration, '{http://maven.apache.org/POM/4.0.0}embeddeds')
                            print("Created new embeddeds element")
                        update_embeddeds(embeddeds, artifactArgs, namespaces)
                    break

    tree.write('all/pom.xml', pretty_print=True, xml_declaration=True, encoding='UTF-8')
    print("POM file updated successfully.")

def check_write_permission(file_path):
    return os.access(file_path, os.W_OK)

if __name__ == '__main__':
    file_path = 'all/pom.xml'
    if check_write_permission(file_path):
        print(f"Write permission is granted for {file_path}.")
    else:
        print(f"Write permission is denied for {file_path}.")
        exit(1)

    parser = argparse.ArgumentParser(description='Update Maven POM file.')
    parser.add_argument('groupId', help='Group ID of the Maven artifact')
    parser.add_argument('artifactId', help='Artifact ID of the Maven artifact')
    parser.add_argument('version', help='Version of the Maven artifact')
    parser.add_argument('url', help='URL to download the Maven artifact')
    parser.add_argument('--scope', required=False, default='provided', help='Scope of the Maven artifact')
    parser.add_argument('--action', required=False, default='add/update', choices=['add/update', 'delete'], help='Action to perform')
    parser.add_argument('--targetPath', required=False, default='/apps/practicemain-packages/install', help='Target path for the embedded artifact')
    parser.add_argument('--artifactResolution', required=False, default='default', choices=['default', 'download'], help='Nature of artifact resolution')
    parser.add_argument('--type', default='zip', required=False, help='Type of the Maven artifact')
    parser.add_argument('--classifier', required=False, help='Classifier of the Maven artifact')
    args = vars(parser.parse_args())
    validate_args(args)
    update_pom(args)