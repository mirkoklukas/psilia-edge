from setuptools import setup

package_name = "psilia_runtime"

setup(
    name=package_name,
    version="0.0.1",
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/default.launch.py"]),
        (f"share/{package_name}/config", ["config/params.yaml"]),
    ],
    install_requires=["setuptools"],
    entry_points={
        "console_scripts": [
            "core_node = psilia_runtime.nodes.core_node:main",
            "camera_node = psilia_runtime.nodes.camera_node:main",
            "ping_node = psilia_runtime.nodes.ping_node:main",
            "recording_node = psilia_runtime.nodes.recording_node:main",
            "depth_node = psilia_runtime.nodes.depth_node:main",
            "depth_cuda_node = psilia_runtime.nodes.depth_cuda_node:main",
            "depth_preview_node = psilia_runtime.nodes.depth_preview_node:main",
            "preview_node = psilia_runtime.nodes.preview_node:main",
            "rectify_node = psilia_runtime.nodes.rectify_node:main",
        ],
    },
    packages=[package_name, f"{package_name}.nodes"],
)
