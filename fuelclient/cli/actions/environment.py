#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import sys

import six

from fuelclient.cli.actions.base import Action
from fuelclient.cli.actions.base import check_all
from fuelclient.cli.actions.base import check_any
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.cli.formatting import format_table
from fuelclient.objects.environment import Environment


class EnvironmentAction(Action):
    """Create, list and modify currently existing environments(clusters)
    """
    action_name = "environment"

    def __init__(self):
        super(EnvironmentAction, self).__init__()
        self.args = [
            Args.get_env_arg(),
            group(
                Args.get_list_arg(
                    "List all available environments"
                ),
                Args.get_set_arg(
                    "Set environment parameters e.g., its name"
                ),
                Args.get_delete_arg(
                    "Delete environment with a specific id or name"
                ),
                Args.get_create_arg(
                    "Create a new environment with "
                    "specific release id and name"
                ),
            ),
            Args.get_release_arg(
                "Release id"
            ),
            Args.get_force_arg(
                "Do it anyway"
            ),
            Args.get_name_arg(
                "Environment name"
            ),
            Args.get_nst_arg(
                "Set network segment type"
            ),
            Args.get_deployment_tasks_arg("Environment tasks configuration"),
            Args.get_attributes_arg("Environment attributes"),
            group(
                Args.get_download_arg(
                    "Download configuration of specific cluster"),
                Args.get_upload_arg(
                    "Upload configuration to specific cluster")
            ),
            Args.get_dir_arg(
                "Select directory to which download release attributes"),
        ]
        self.flag_func_map = (
            ("deployment-tasks", self.deployment_tasks),
            ("attributes", self.attributes),
            ("create", self.create),
            ("set", self.set),
            ("delete", self.delete),
            (None, self.list)
        )

    @check_all("name", "release")
    def create(self, params):
        """To create an environment with name MyEnv and release id=1 run:
                fuel env create --name MyEnv --rel 1

            By default, it creates environment setting neutron with VLAN
            network segmentation as network provider
            To specify other modes add optional arguments:
                fuel env create --name MyEnv --rel 1 --net-segment-type vlan
        """

        if params.nst == 'gre':
            six.print_(
                "WARNING: GRE network segmentation type is deprecated "
                "since 7.0 release.", file=sys.stderr)

        env = Environment.create(
            params.name,
            params.release,
            params.nst,
        )

        data = env.get_fresh_data()

        self.serializer.print_to_output(
            data,
            u"Environment '{name}' with id={id} was created!"
            .format(**data)
        )

    @check_all("env")
    def set(self, params):
        """To change environment name:
                fuel --env 1 env set --name NewEnvName
        """
        acceptable_params = ('name', )

        env = Environment(params.env, params=params)

        # forming message for output and data structure for request body
        # TODO(aroma): make it less ugly
        msg_template = ("Following attributes are changed for "
                        "the environment: {env_attributes}")

        env_attributes = []
        update_kwargs = dict()
        for param_name in acceptable_params:
            attr_value = getattr(params, param_name, None)
            if attr_value:
                update_kwargs[param_name] = attr_value
                env_attributes.append(
                    ''.join([param_name, '=', str(attr_value)])
                )

        data = env.set(update_kwargs)
        env_attributes = ', '.join(env_attributes)
        self.serializer.print_to_output(
            data,
            msg_template.format(env_attributes=env_attributes)
        )

    @check_all("env")
    def delete(self, params):
        """To delete the environment:
                fuel --env 1 env --force delete
        """
        env = Environment(params.env, params=params)

        if env.status == "operational" and not params.force:
            self.serializer.print_to_output(env.data,
                                            "Deleting an operational"
                                            "environment is a dangerous "
                                            "operation. Please use --force to "
                                            "bypass this message.")
            return

        data = env.delete()
        self.serializer.print_to_output(
            data,
            "Environment with id={0} was deleted"
            .format(env.id)
        )

    def list(self, params):
        """Print all available environments:
                fuel env
        """
        acceptable_keys = ("id", "status", "name", "release_id", )
        data = Environment.get_all_data()
        if params.env:
            data = filter(
                lambda x: x[u"id"] == int(params.env),
                data
            )
        self.serializer.print_to_output(
            data,
            format_table(
                data,
                acceptable_keys=acceptable_keys
            )
        )

    @check_all("env")
    @check_any("download", "upload")
    def deployment_tasks(self, params):
        """Modify deployment_tasks for environment:
                fuel env --env 1 --deployment-tasks --download
                fuel env --env 1 --deployment-tasks --upload
        """
        cluster = Environment(params.env)
        dir_path = self.full_path_directory(
            params.dir, 'cluster_{0}'.format(params.env))
        full_path = '{0}/deployment_tasks'.format(dir_path)
        if params.download:
            tasks = cluster.get_deployment_tasks()
            self.serializer.write_to_path(full_path, tasks)
            print("Deployment tasks for cluster {0} "
                  "downloaded into {1}.yaml.".format(cluster.id, full_path))
        elif params.upload:
            tasks = self.serializer.read_from_file(full_path)
            cluster.update_deployment_tasks(tasks)
            print("Deployment tasks for cluster {0} "
                  "uploaded from {1}.yaml".format(cluster.id, full_path))

    @check_all("env")
    @check_any("download", "upload")
    def attributes(self, params):
        """Modify attributes of the environment:
                fuel env --env 1 --attributes --download
                fuel env --env 1 --attributes --upload
        """
        cluster = Environment(params.env)
        dir_path = self.full_path_directory(
            params.dir, 'cluster_{0}'.format(params.env))
        full_path = '{0}/attributes'.format(dir_path)

        if params.download:
            attributes = cluster.get_attributes()
            self.serializer.write_to_path(full_path, attributes)
            print("Attributes of cluster {0} "
                  "downloaded into {1}.yaml.".format(cluster.id, full_path))
        elif params.upload:
            attributes = self.serializer.read_from_file(full_path)
            cluster.update_attributes(attributes, params.force)
            print("Attributes of cluster {0} "
                  "uploaded from {1}.yaml".format(cluster.id, full_path))
