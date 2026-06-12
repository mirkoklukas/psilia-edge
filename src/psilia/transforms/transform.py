import warnings
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from jax.scipy.spatial.transform import Rotation as Rot
from jax.tree_util import register_pytree_node_class
from rich.console import Console

from psilia.utils import load_yaml, save_yaml

console = Console()


def multiply_quats(q1, q2):
    return (Rot.from_quat(q1) * Rot.from_quat(q2)).as_quat()


def so3_exp(w: jax.Array) -> jax.Array:
    """SO(3) exponential map: axis-angle vector to unit quaternion (xyzw).

    Given w ∈ R³ with θ = ||w||, the quaternion is:

        q = [sin(θ/2)/θ · w,  cos(θ/2)]

    See https://www.user.tu-berlin.de/mtoussai/notes/quaternions.pdf

    Args:
        w: Axis-angle vector (..., 3). The direction is the rotation axis,
           the norm is the rotation angle in radians.

    Returns:
        Unit quaternion (..., 4) in xyzw convention.
    """
    theta = jnp.linalg.norm(w, axis=-1, keepdims=True)
    half_theta = theta / 2.0
    # sin(θ/2)/θ → 1/2 as θ → 0
    k = jnp.where(theta < 1e-6, 0.5, jnp.sin(half_theta) / theta)
    xyz = w * k
    w_scalar = jnp.cos(half_theta)
    return jnp.concatenate([xyz, w_scalar], axis=-1)


def load_transforms(path: Path, glob_pattern: str = "*.transform.yaml"):
    transforms = []
    for file in path.glob(glob_pattern):
        transforms.append(Transform.load(file))
    return transforms


def sample_ball_uniform(key: jax.Array, n: int, r: float = 1.0) -> jax.Array:
    """Sample n points uniformly from a 3D ball of radius r.

    Uses the rejection-free method: sample a direction uniformly on S²
    and a radius from p(s) ∝ s² via inverse CDF (s = r · u^{1/3}).

    Args:
        key: JAX PRNG key.
        n: Number of points to sample.
        r: Radius of the ball.

    Returns:
        Points (n, 3) uniformly distributed in the ball.
    """
    key_dir, key_r = jax.random.split(key)
    direction = jax.random.normal(key_dir, shape=(n, 3))
    direction = direction / jnp.linalg.norm(direction, axis=-1, keepdims=True)
    u = jax.random.uniform(key_r, shape=(n, 1))
    radius = r * u ** (1.0 / 3.0)
    return radius * direction


def sample_transforms_uniform(
    key: jax.Array,
    n: int,
    t_bounds: float | jax.Array = 1.0,
    w_bounds: float | jax.Array = jnp.pi,
    *,
    parent: str | None = None,
    child: str | None = None,
):
    """Sample random transforms with uniform translation and rotation.

    Args:
        key: JAX PRNG key.
        n: Number of transforms to sample.
        t_bounds: Half-extent for uniform translation sampling.
            Scalar or (3,) array for per-axis bounds.
        w_bounds: Half-extent for uniform axis-angle sampling.
            Scalar or (3,) array for per-axis bounds.
        parent: Parent frame name.
        child: Child frame name.
    """
    key_t, key_w = jax.random.split(key)
    t = jax.random.uniform(key_t, shape=(n, 3), minval=-t_bounds, maxval=t_bounds)
    w = jax.random.uniform(key_w, shape=(n, 3), minval=-w_bounds, maxval=w_bounds)
    q = so3_exp(w)
    return Transform(t, q, parent=parent, child=child)


@register_pytree_node_class
class Transform:
    """
    A Transform is an element of the special Euclidean group SE(3), and
    describes the relative position and orientation of a child coordinate frame
    in 3D space relative to a parent coordinate frame.

    It defines a mapping from the *child* frame to the *parent* frame.

    We store quaternions as (x,y,z,w), i.e. `scalar_first = False`
    for scipy's Rotation class.

    Example:
    ```
    world_from_lidar = Transform(
        translation=[0, 0, 0],
        quaternion=[0, 0, 0, 1],
        parent="world",
        child="lidar",
    )
    # Points in the lidar frame
    xs = jnp.random.normal(key, (100, 3))

    # Points in the world frame
    ys = world_from_lidar(xs)
    ```
    """

    def __init__(
        self,
        translation: jax.Array,
        quaternion: jax.Array,
        *,
        parent: str | None = None,
        child: str | None = None,
    ):
        """
        Args:
            translation: 3D Translation vector
            quaternion: 4D Quaternion vector saved as xyzw.
            parent: The name of the **parent** coordinate frame.
            child: The name of the **child** coordinate frame.
        """
        self.translation: jax.Array = translation
        self.quaternion: jax.Array = quaternion
        self.parent: str | None = parent
        self.child: str | None = child

    @property
    def child_frame_id(self):
        """
        Returns the source frame id.
        Mostly to be compatible with the old API.
        """
        return self.child

    @child_frame_id.setter
    def child_frame_id(self, value):
        self.child = value

    @property
    def frame_id(self):
        """
        Returns the target frame id.
        Mostly to be compatible with the old API.
        """
        return self.parent

    @frame_id.setter
    def frame_id(self, value):
        self.parent = value

    @staticmethod
    def id(*, parent=None, child=None):
        """Identity transform."""
        return Transform(
            jnp.zeros(3),
            jnp.array([0.0, 0.0, 0.0, 1.0]),
            parent=parent,
            child=child,
        )

    # Jax Pytree Registration
    def tree_flatten(self):
        return (
            (self.translation, self.quaternion),
            {"parent": self.parent, "child": self.child},
        )

    # Jax Pytree Registration
    @classmethod
    def tree_unflatten(cls, aux_data, children):
        return cls(*children, **aux_data)

    @property
    def rot(self) -> Rot:
        """Returns the rotation as a Rotation object."""
        if isinstance(self.quaternion, jax.Array):
            return Rot.from_quat(self.quaternion)
        else:
            return Rot.from_quat(jnp.asarray(self.quaternion))

    @property
    def t(self) -> jax.Array:
        """Returns the translation."""
        return self.translation

    @t.setter
    def t(self, t: jax.Array):
        self.translation = t

    @property
    def q(self) -> jax.Array:
        """Returns the quaternion."""
        return self.quaternion

    @q.setter
    def q(self, q: jax.Array):
        self.quaternion = q

    @property
    def R(self):
        """Returns the rotation matrix."""
        return self.rot.as_matrix()

    @property
    def quat(self):
        """Returns the quaternion."""
        return self.quaternion

    @property
    def xyzw(self):
        return self.quaternion

    @property
    def wxyz(self):
        xyzw = self.xyzw
        return jnp.array([xyzw[..., -1], *xyzw[..., :3]])

    def apply(self, xs: jax.Array):
        """Apply the transform to a set of points.
        Args:
            xs: Points to transform. Needs to be broadcastable
                with the transform's shape.
        Returns:
            Transformed points.
        """
        return Rot.from_quat(self.q).apply(xs) + self.t

    def __call__(self, xs):
        """Apply the transform to a set of points.
        Args:
            xs: Points to transform. Needs to be broadcastable
                with the transform's shape.
        Returns:
            Transformed points.
        """
        return self.apply(xs)

    def inv(self):
        """Inverse transform."""
        R_inv = Rot.from_quat(self.q).inv()
        return Transform(
            -R_inv.apply(self.t),
            R_inv.as_quat(),
            parent=self.child,
            child=self.parent,
        )

    def _chain(self, other):
        r"""
        Transformation that first applies `self` and then `other`. That means
        the resulting transformation maps `x` to `other(self(x))`.

        That means if `self` is a transform from `A` to `B`, and `other` is a
        transform from `B` to `C`, then `self.chain(other)` is a transform
        from `A` to `C`, namely the transformation from "chaining" the two
        together: `A --self--> B --other--> C`.

        From a pose tree perspective it describes the transform from a child
        `A` to its grandparent `C` - through its parent `B`.
        """
        if (
            ((self.parent is not None) and (self.parent != ""))
            and ((other.child is not None) and (other.child != ""))
            and (self.parent != other.child)
        ):
            msg = (
                "Target and source frames don't match: "
                + f"`{self.child}` --> `{self.parent}` != "
                + f"`{other.child}` --> `{other.parent}`"
            )
            # Warn rather than raise: mismatched frames are sometimes
            # intentional. Use `raise ValueError(msg)` here to enforce frame
            # consistency strictly.
            warnings.warn(msg)

        # Note:
        # (1) If q is a unit quaternion and Q the associated rotation matrix then
        #   for a 3D vector x we have $Qx = q * (x,0)^T * q^{-1}$. Thus the rotation
        #   matrix PQ is associated to the product $pq$ of their associated quaternions.
        # (2) The translation vector of a transform $f$ is simply $f(0)$;
        #   thus for a composition $(g \circ f)$ it is $g(f(0))$.
        return Transform(
            other.apply(self.t),
            multiply_quats(other.q, self.q),
            parent=other.parent,
            child=self.child,
        )

    def _compose(self, other):
        """Compose this transform with another transform.
        Same as matrix product of the two transforms, but without converting to matrices.
        """
        return other._chain(self)

    def __matmul__(self, other):
        return self._compose(other)

    def _matmul(self, other):
        """
        Syntactic sugar for `compose`.

        Mimics the matrix multiplication of two transforms. That means we have
        `(self @ other).as_matrix() == self.as_matrix() @ other.as_matrix()`.

        From a pose tree perspective it appends `other` as a "child" of `self`.
        """
        # NOTE: this is less stable than the quaternion composition in _compose,
        #   but it is a good sanity check that the two are consistent.
        if (
            ((self.child is not None) and (self.child != ""))
            and ((other.parent is not None) and (other.parent != ""))
            and (self.child != other.parent)
        ):
            msg = (
                "Child and parent frames don't match: "
                + f"`{self.parent}` <-- `{self.child}` != "
                + f"`{other.parent}` <-- `{other.child}`"
            )
            # Warn rather than raise: mismatched frames are sometimes
            # intentional. Use `raise ValueError(msg)` here to enforce frame
            # consistency strictly.
            warnings.warn(msg)

        return Transform.from_matrix(
            self.as_matrix() @ other.as_matrix(), parent=self.parent, child=other.child
        )

    def __rshift__(self, other):
        """
        Syntactic sugar for `other @ self`. It indicates the
        flow of data through `self` first, followed by `other`.
        """
        return other @ self

    def __lshift__(self, other):
        """
        Syntactic sugar for `self @ other`. It indicates the
        flow of data through `other` first, followed by `self`.
        """
        return self @ other

    def as_matrix(self):
        """
        Convert the transform to a 4x4 matrix `P = [R t; 0 1]`.
        """
        if len(self) == 0:
            R = self.rot.as_matrix()
            t = self.t

            return jnp.array(
                [
                    [R[0, 0], R[0, 1], R[0, 2], t[0]],
                    [R[1, 0], R[1, 1], R[1, 2], t[1]],
                    [R[2, 0], R[2, 1], R[2, 2], t[2]],
                    [0, 0, 0, 1],
                ]
            )
        else:
            R = self.rot.as_matrix()
            t = self.t
            hom = jnp.repeat(jnp.array([[[0.0, 0.0, 0.0, 1.0]]]), len(self), axis=0)
            return jnp.concatenate(
                [
                    jnp.concatenate(
                        [
                            R,
                            t[..., :, None],
                        ],
                        axis=-1,
                    ),
                    hom,
                ],
                axis=-2,
            )

    @classmethod
    def from_matrix(
        cls,
        P,
        *,
        parent=None,
        child=None,
    ):
        """
        Create a transform from a 4x4 matrix `P = [R t; 0 1]`.
        """
        t = jnp.array(P[..., :3, 3])
        q = Rot.from_matrix(P[..., :3, :3]).as_quat()
        return cls(t, q, parent=parent, child=child)

    @classmethod
    def from_tR(cls, t, R, *, parent=None, child=None):
        return cls(t, Rot.from_matrix(R).as_quat(), parent=parent, child=child)

    @classmethod
    def from_te(cls, t, e, *, parent=None, child=None, seq="xyz", degrees=False):
        return cls(
            t,
            Rot.from_euler(seq, e, degrees=degrees).as_quat(),
            parent=parent,
            child=child,
        )

    # # # # # # # # # # # # # # # # # # # # # # #
    #
    #   Saving and loading transforms
    #
    # # # # # # # # # # # # # # # # # # # # # # #

    def save(self, fname, rotation_type="QUAT", seq="XYZ", degrees=True):
        """Save the transform as yaml file."""
        save_yaml(
            self.as_dict(rotation_type=rotation_type, seq=seq, degrees=degrees), fname
        )

    @classmethod
    def load(cls, fname):
        """Load the transform from a yaml file."""
        return cls.from_dict(load_yaml(fname))

    def as_dict(
        self,
        rotation_type="QUAT",
        seq="XYZ",
        degrees=True,
        frame_type="PARENT_CHILD",
    ):
        """
        Returns a dictionary representation of the transform.

        Args:
            rotation_type: "QUAT" (default), "EULER" (roll, pitch, yaw)
            seq: If rotation_type is "EULER", the sequence of euler angles (default: "XYZ")
            degrees: If rotation_type is "EULER", whether the unit of euler angles is degrees (default: True)
            flat: Whether to store a flat dictionary (default: True)
            frame_type: "PARENT_CHILD" (default), "SOURCE_TARGET"

        Returns:
            Dictionary representation of the transform.
        """
        if frame_type != "PARENT_CHILD":
            raise ValueError(f"Invalid frame type: {frame_type}")
        # if len(self) != 0:
        # raise ValueError("Can only convert SINGLE transforms to dictionary")

        transform = {
            "parent_frame_id": self.parent,
            "child_frame_id": self.child,
        }

        tx = np.array(self.t[..., 0]).tolist()
        ty = np.array(self.t[..., 1]).tolist()
        tz = np.array(self.t[..., 2]).tolist()
        translation = {
            "x": tx,
            "y": ty,
            "z": tz,
        }

        rotation = {}
        if rotation_type.upper() == "EULER":
            e = np.array(self.rot.as_euler(seq, degrees=degrees))
            roll = np.array(e[..., 0]).tolist()
            pitch = np.array(e[..., 1]).tolist()
            yaw = np.array(e[..., 2]).tolist()
            rotation = {
                "roll": roll,  # Rot around x-axis (roll)
                "pitch": pitch,  # Rot around y-axis (pitch)
                "yaw": yaw,  # Rot around z-axis (yaw)
                "seq": seq,
                "degrees": degrees,
            }
        elif rotation_type.upper() == "QUAT":
            qx = np.array(self.q[..., 0]).tolist()
            qy = np.array(self.q[..., 1]).tolist()
            qz = np.array(self.q[..., 2]).tolist()
            qw = np.array(self.q[..., 3]).tolist()
            rotation = {
                "qx": qx,
                "qy": qy,
                "qz": qz,
                "qw": qw,
            }
        else:
            raise ValueError(f"Invalid rotation type: {rotation_type}")

        transform.update({"translation": translation})
        transform.update({"rotation": rotation})

        return transform

    @classmethod
    def from_dict(cls, tf_dict):  # noqa: PLR0912
        """Load a transform from a dictionary."""
        # TODO: Refactor from_dict to reduce branch complexity.
        # TODO: Write utility to extract nested keys from dict.

        # Get translation
        if isinstance(tf_dict["translation"], dict):
            translation = tf_dict["translation"]
            tx = translation["x"]
            ty = translation["y"]
            tz = translation["z"]
            t = jnp.stack(jnp.array([tx, ty, tz]), axis=-1)
        else:
            t = jnp.array(tf_dict["translation"])

        # if "quaternion" in tf_dict:
        # q = jnp.array(tf_dict["quaternion"])

        if "rotation" in tf_dict:
            rotation = tf_dict["rotation"]
        elif "quaternion" in tf_dict:
            rotation = tf_dict["quaternion"]
        else:
            raise ValueError(f"Cannot parse rotation from dictionary: {tf_dict}")

        # Get rotation
        if isinstance(rotation, dict):
            if "qx" in rotation:
                qx = rotation["qx"]
                qy = rotation["qy"]
                qz = rotation["qz"]
                qw = rotation["qw"]
                q = jnp.stack(jnp.array([qx, qy, qz, qw]), axis=-1)
            elif "x" in rotation:
                qx = rotation["x"]
                qy = rotation["y"]
                qz = rotation["z"]
                qw = rotation["w"]
                q = jnp.stack(jnp.array([qx, qy, qz, qw]), axis=-1)
            elif "roll" in rotation:
                roll = rotation["roll"]
                pitch = rotation["pitch"]
                yaw = rotation["yaw"]
                q = jnp.stack(jnp.array([roll, pitch, yaw]), axis=-1)
                q = Rot.from_euler(
                    rotation["seq"], q, degrees=rotation["degrees"]
                ).as_quat()
            else:
                raise ValueError(f"Cannot parse rotation from dictionary: {tf_dict}")
        else:
            q = jnp.array(rotation)

        parent = None
        child = None
        if "parent_frame_id" in tf_dict:
            parent = tf_dict["parent_frame_id"]
            child = tf_dict["child_frame_id"]
        elif "frame_id" in tf_dict:
            parent = tf_dict["frame_id"]
            child = tf_dict["child_frame_id"]
        elif "parent" in tf_dict:
            parent = tf_dict["parent"]
            child = tf_dict["child"]

        return cls(
            translation=t,
            quaternion=q,
            parent=parent,
            child=child,
        )

    # # # # # # # # # # # # # # # # # # # # # # #
    #
    #   Utility functions when dealing with
    #   transforms as pytree nodes
    #
    # # # # # # # # # # # # # # # # # # # # # # #
    @property
    def shape(self) -> tuple:
        return self.translation.shape[:-1]

    def __len__(self) -> int:
        if len(self.translation.shape) == 1:
            return 0
        else:
            return self.translation.shape[0]

    def __iter__(self):
        self.current = 0
        return self

    def __next__(self):
        if self.current < len(self):
            ret = self[self.current]
            self.current += 1
            return ret
        else:
            raise StopIteration

    def __getitem__(self, index):
        return Transform(
            self.t[index],
            self.q[index],
            parent=self.parent,
            child=self.child,
        )

    # TODO: This is a "homogeneous" stack of transforms with the same parent and child
    #   Should we enable a "in-homogeneous" stack? Then we'd have to adjust getitem
    #   and think of if and how all operations make sense.
    @staticmethod
    def stack(tfs: list):
        """Stack a list of transforms.
        Args:
            tfs: List of transforms.
        Returns:
            Stacked transform.
        """
        parent = tfs[0].parent
        child = tfs[0].child
        assert all(tf.parent == parent for tf in tfs), (
            "All transforms must have the same parent"
        )
        assert all(tf.child == child for tf in tfs), (
            "All transforms must have the same child"
        )
        return Transform(
            jnp.stack([tf.t for tf in tfs]),
            jnp.stack([tf.q for tf in tfs]),
            parent=parent,
            child=child,
        )

    # # # # # # # # # # # # # # # # # # # # # # #
    #
    #   String representation of the transform
    #
    # # # # # # # # # # # # # # # # # # # # # # #

    def __str__(self) -> str:
        t = self.t
        e = self.rot.as_euler("XYZ", degrees=True).astype(int)

        return (
            "Transform("
            f"\n translation={t},"
            f"\n quaternion={self.q},"
            f"\n euler (XYZ°)={e}"
            f"\n): '{self.parent}' ↩ '{self.child}'."
        )

    def __rich__(self):
        t = self.t
        e = self.rot.as_euler("XYZ", degrees=True).astype(int)

        return (
            "[bold]Transform[/bold]("
            f"\n translation={t},"
            f"\n quaternion={self.q},"
            f"\n euler={e} (XYZ°)"
            f"\n): [bold]'{self.parent}'[/bold] ↩ [bold]'"
            f"{self.child}'[/bold]."
        )

    def __repr__(self) -> str:
        t = self.t
        e = self.rot.as_euler("XYZ", degrees=True).astype(int)

        return (
            "Transform("
            f"\n translation={t},"
            f"\n quaternion={self.q},"
            f"\n euler={e} (XYZ°)"
            f"\n): '{self.parent}' ↩ '{self.child}'."
        )


Pose = Transform


# Transform of a camera at the
# origin pointing along the x-axis
CAM_ALONG_X = Transform.from_tR(
    jnp.array([0.0, 0.0, 0.0]),
    jnp.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]),
)
