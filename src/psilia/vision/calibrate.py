import subprocess
from pathlib import Path

from psilia.utils import console, get_root_dir

__all__ = [
    "run_kalibr",
]


def run_kalibr(
    mcap: Path = Path("./"),
    output: Path = Path("./results"),
    topic: str = "/sensor/camera/front/image_raw/compressed",
    april_tags: Path = Path("./april_tags.yaml"),
):
    """
    Wrapper to run kalibr to calibrate the camera.

    Args:
        mcap: Path to the mcap folder containing the mcap file and the april tags file.
        output: Path to the output folder. Calibration and visualization results
                will be saved here.
        topic: Image topic to use for calibration.
        april_tags: Path to the april tags file.

    """
    console.print("\n[bold]Calibrating camera[/bold] using kalibr\n")

    mcap = Path(mcap).resolve()
    output = Path(output).resolve()
    april_tags = Path(april_tags).resolve()
    topic = str(topic)

    output.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Handing over to kalibr script ... [/bold]")

    # TODO: remove call to script and call the commands directly from here
    cmd = [
        get_root_dir() / "scripts/calibration/kalibr.sh",
        mcap,
        "--results_folder",
        output,
        "--april_tags",
        april_tags,
        "--topic",
        topic,
    ]
    cmd = list(map(str, cmd))
    subprocess.check_call(cmd)

    console.print("[bold]Done![/bold]")
