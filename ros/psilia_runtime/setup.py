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
            "mock_node = psilia_runtime.nodes.mock_node:main",
            "depth_node = psilia_runtime.nodes.depth_node:main",
            "pose_node = psilia_runtime.nodes.pose_node:main",
        ],
    },
    packages=[package_name, f"{package_name}.nodes"],
)
