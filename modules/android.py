import glob
import os
import tarfile
from subprocess import check_call

import modules.config as c
import modules.functions as f


def run_task_build_pdfium():
    f.debug("Building PDFium...")

    target = "android"
    build_dir = os.path.join("build", target)
    f.create_dir(build_dir)

    target_dir = os.path.join(build_dir, "pdfium")
    f.remove_dir(target_dir)

    cwd = build_dir
    command = " ".join(
        [
            "gclient",
            "config",
            "--unmanaged",
            "https://pdfium.googlesource.com/pdfium.git",
        ]
    )
    check_call(command, cwd=cwd, shell=True)

    gclient_file = os.path.join(build_dir, ".gclient")
    f.append_to_file(gclient_file, "target_os = [ 'android' ]")

    cwd = build_dir
    command = " ".join(["gclient", "sync"])
    check_call(command, cwd=cwd, shell=True)

    cwd = target_dir
    command = " ".join(["git", "checkout", c.pdfium_git_commit])
    check_call(command, cwd=cwd, shell=True)


def run_task_patch():
    f.debug("Patching...")

    source_dir = os.path.join("build", "android", "pdfium")

    # build gn
    source_file = os.path.join(
        source_dir,
        "BUILD.gn",
    )
    if f.file_line_has_content(source_file, 26, "  ]\n"):
        f.replace_line_in_file(source_file, 26, '    "FPDFSDK_EXPORTS",\n  ]\n')

        f.debug("Applied: Build GN")
    else:
        f.debug("Skipped: Build GN")

    # build gn flags
    source_file = os.path.join(
        source_dir,
        "BUILD.gn",
    )
    if f.file_line_has_content(source_file, 19, "  cflags = []\n"):
        f.replace_line_in_file(
            source_file, 19, '  cflags = [ "-fvisibility=default" ]\n'
        )

        f.debug("Applied: Build GN Flags")
    else:
        f.debug("Skipped: Build GN Flags")


def run_task_build():
    f.debug("Building libraries...")

    current_dir = os.getcwd()

    # configs
    for config in c.configurations_android:
        # targets
        for target in c.targets_android:
            main_dir = os.path.join(
                "build",
                target["target_os"],
                "pdfium",
                "out",
                "{0}-{1}-{2}".format(target["target_os"], target["target_cpu"], config),
            )

            f.remove_dir(main_dir)
            f.create_dir(main_dir)

            os.chdir(
                os.path.join(
                    "build",
                    target["target_os"],
                    "pdfium",
                )
            )

            # generating files...
            f.debug(
                'Generating files to arch "{0}" and configuration "{1}"...'.format(
                    target["target_cpu"], config
                )
            )

            arg_is_debug = "true" if config == "debug" else "false"

            args = []
            args.append('target_os="{0}"'.format(target["pdfium_os"]))
            args.append('target_cpu="{0}"'.format(target["target_cpu"]))
            args.append("use_goma=false")
            args.append("is_debug={0}".format(arg_is_debug))
            args.append("pdf_use_skia=false")
            args.append("pdf_use_skia_paths=false")
            args.append("pdf_enable_xfa=false")
            args.append("pdf_enable_v8=false")
            args.append("is_component_build=true")
            args.append("pdf_is_standalone=true")
            args.append("pdf_bundle_freetype=true")

            if config == "release":
                args.append("symbol_level=0")

            args_str = " ".join(args)

            command = " ".join(
                [
                    "gn",
                    "gen",
                    "out/{0}-{1}-{2}".format(
                        target["target_os"], target["target_cpu"], config
                    ),
                    "--args='{0}'".format(args_str),
                ]
            )
            check_call(command, shell=True)

            # compiling...
            f.debug(
                'Compiling to arch "{0}" and configuration "{1}"...'.format(
                    target["target_cpu"], config
                )
            )

            command = " ".join(
                [
                    "ninja",
                    "-C",
                    "out/{0}-{1}-{2}".format(
                        target["target_os"], target["target_cpu"], config
                    ),
                    "pdfium",
                    "-v",
                ]
            )
            check_call(command, shell=True)

            os.chdir(current_dir)


def run_task_install():
    f.debug("Installing libraries...")

    # configs
    for config in c.configurations_android:
        f.remove_dir(os.path.join("build", "android", config))
        f.create_dir(os.path.join("build", "android", config))

        # targets
        for target in c.targets_android:
            out_dir = "{0}-{1}-{2}".format(
                target["target_os"], target["target_cpu"], config
            )

            source_lib_dir = os.path.join("build", "android", "pdfium", "out", out_dir)

            lib_dir = os.path.join("build", "android", config, "lib")
            target_dir = os.path.join(lib_dir, target["android_cpu"])

            f.remove_dir(target_dir)
            f.create_dir(target_dir)

            for basename in os.listdir(source_lib_dir):
                if basename.endswith(".so"):
                    pathname = os.path.join(source_lib_dir, basename)

                    if os.path.isfile(pathname):
                        f.copy_file2(pathname, target_dir)

        # include
        include_dir = os.path.join("build", "android", "pdfium", "public")
        target_include_dir = os.path.join("build", "android", config, "include")
        f.remove_dir(target_include_dir)
        f.create_dir(target_include_dir)

        for basename in os.listdir(include_dir):
            if basename.endswith(".h"):
                pathname = os.path.join(include_dir, basename)

                if os.path.isfile(pathname):
                    f.copy_file2(pathname, target_include_dir)


def run_task_test():
    f.debug("Testing...")

    for config in c.configurations_android:
        for target in c.targets_android:
            lib_dir = os.path.join(
                "build", "android", config, "lib", target["android_cpu"]
            )

            command = " ".join(["file", os.path.join(lib_dir, "libpdfium.so")])
            check_call(command, shell=True)


def run_task_archive():
    f.debug("Archiving...")

    current_dir = os.getcwd()
    lib_dir = os.path.join(current_dir, "build", "android")
    output_filename = os.path.join(current_dir, "android.tgz")

    tar = tarfile.open(output_filename, "w:gz")

    for configuration in c.configurations_android:
        tar.add(
            name=os.path.join(lib_dir, configuration),
            arcname=os.path.basename(os.path.join(lib_dir, configuration)),
            filter=lambda x: (
                None
                if "_" in x.name
                and not x.name.endswith(".h")
                and not x.name.endswith(".so")
                and os.path.isfile(x.name)
                else x
            ),
        )

    tar.close()
