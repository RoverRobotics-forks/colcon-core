# Copyright 2016-2018 Dirk Thomas
# Licensed under the Apache License, Version 2.0

from collections import OrderedDict
from pathlib import Path
import sys

from colcon_core import shell
from colcon_core.plugin_system import satisfies_version
from colcon_core.plugin_system import SkipExtensionException
from colcon_core.shell import get_environment_variables
from colcon_core.shell import logger
from colcon_core.shell import ShellExtensionPoint
from colcon_core.shell.template import expand_template


class BatShell(ShellExtensionPoint):
    """Generate `.bat` scripts to extend the environment."""

    # the priority needs to be higher than the default for primary shells
    PRIORITY = 200

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(ShellExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')
        if sys.platform != 'win32' and not shell.use_all_shell_extensions:
            raise SkipExtensionException('Not used on non-Windows systems')

    def create_prefix_script(
        self, prefix_path, pkg_names, merge_install
    ):  # noqa: D102
        prefix_env_path = prefix_path / 'prefix.bat'
        logger.info("Creating prefix script '%s'" % prefix_env_path)
        expand_template(
            Path(__file__).parent / 'template' / 'prefix.bat.em',
            prefix_env_path,
            {
                'pkg_names': pkg_names,
                'merge_install': merge_install,
            })

    def create_package_script(
        self, prefix_path, pkg_name, hooks
    ):  # noqa: D102
        pkg_env_path = prefix_path / 'share' / pkg_name / 'package.bat'
        logger.info("Creating package script '%s'" % pkg_env_path)
        expand_template(
            Path(__file__).parent / 'template' / 'package.bat.em',
            pkg_env_path,
            {
                'hooks': list(filter(
                    lambda hook: str(hook[0]).endswith('.bat'), hooks)),
            })

    def create_hook_prepend_value(
        self, env_hook_name, prefix_path, pkg_name, name, subdirectory,
    ):  # noqa: D102
        hook_path = prefix_path / 'share' / pkg_name / 'hook' / \
            ('%s.bat' % env_hook_name)
        logger.info("Creating environment hook '%s'" % hook_path)
        expand_template(
            Path(__file__).parent / 'template' / 'hook_prepend_value.bat.em',
            hook_path,
            {
                'name': name,
                'subdirectory': subdirectory,
            })
        return hook_path

    async def generate_command_environment(
        self, task_name, build_base, dependencies,
    ):  # noqa: D102
        if sys.platform != 'win32':
            raise SkipExtensionException('Not usable on non-Windows systems')

        hook_path = build_base / ('colcon_command_prefix_%s.bat' % task_name)
        expand_template(
            Path(__file__).parent / 'template' / 'command_prefix.bat.em',
            hook_path,
            {'dependencies': dependencies})

        # ensure that the referenced scripts exist
        missing = OrderedDict()
        for pkg_name, pkg_install_base in dependencies.items():
            pkg_script = Path(
                pkg_install_base) / 'share' / pkg_name / 'package.bat'
            if not pkg_script.exists():
                missing[pkg_name] = str(pkg_script)
        if missing:
            raise RuntimeError(
                'Failed to find the following files:' +
                ''.join('\n- %s' % path for path in missing.values()) +
                '\nCheck that the following packages have been built:' +
                ''.join('\n- %s' % name for name in missing.keys()))

        cmd = [str(hook_path), '&&', 'set']
        env = await get_environment_variables(cmd, str(build_base))

        # write environment variables to file for debugging
        env_path = build_base / (
            'colcon_command_prefix_%s.bat.env' % task_name)
        with env_path.open('w') as h:
            for key in sorted(env.keys()):
                value = env[key]
                h.write('{key}={value}\n'.format_map(locals()))

        return env