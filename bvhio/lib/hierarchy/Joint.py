import glm
import bisect
from SpatialTransform import Transform, Pose


class Joint(Transform):
    """Spatial definition of an linear space with position, rotation and scale.

    - Bone alignment is expected to be along the Y+ axis.
    - Space is defined as right handed where Y+:up and X+:right and Z-:forward.
    - Positive rotations are counter clockwise.

    - The animation is a cualculation of ``Pose = RestPose + Keyframe``
    - The RestPose and Keyframe data is in local space only.
    - The method ``readPose()`` combines the RestPose and Keframes."""

    @property
    def Parent(self) -> "Joint":
        return self._Parent

    @property
    def Children(self) -> list["Joint"]:
        return self._Children

    @property
    def CurrentFrame(self) -> int:
        """Latest frame index that has been read with readPose()."""
        return self._CurrentFrame

    @property
    def Keyframes(self) -> list[tuple[int, Pose]]:
        """Animation data for the joint. A keyframe holds the change of local properties in relation to the rest pose, so that ``Pose = RestPose + Keyframe``.

    - The first element in the tuple is the frame id and the second element are the local keyframe properties.
    - This is an ordered list by the frame id.
    - Negative frame ids should not exist."""
        return self._Keyframes

    @Keyframes.setter
    def Keyframes(self, value: list[tuple[int, Pose]]) -> None:
        self._Keyframes = list(value)

    @property
    def RestPose(self) -> Pose:
        """Pose without any keyframe applied. The common T-Pose would go here. This Pose is the base for all animation data."""
        return self._RestPose

    @RestPose.setter
    def RestPose(self, value: Pose) -> None:
        self._RestPose = value.duplicate()

    def __init__(
            self, name: str = None,
            position: glm.vec3 = None,
            rotation: glm.quat = None,
            scale: glm.vec3 = None,
            restPose: Pose = None,
            keyFrames: list[tuple[int, Pose]] = None) -> None:

        super().__init__(name, position, rotation, scale)
        self._Parent: "Joint" = None
        self._Children: list["Joint"] = []

        self._RestPose: Pose = Pose() if restPose is None else restPose
        self._Keyframes: list[tuple[int, Pose]] = [] if keyFrames is None else keyFrames
        self._CurrentFrame = -1

    def getKeyframePose(self, frame: int) -> Pose:
        """Returns the pose at the given frame id.

        - If the frame number is negative, it will look for the n-th frame from the end.
        - If there are no keyframes, the joint propetries will not change.
        - If the frame id is out of the keyframe length, the nearest keyframe propetires are used.
        - If the frame id is between two keyframes, pose properties are linearly interpolated."""
        if len(self.Keyframes) == 0: return Pose()
        if frame < 0: frame = max(0, self.getKeyframeRange(includeChildren=False)[1] + 1 - frame)

        # pose definition
        index = bisect.bisect_left([key[0] for key in self.Keyframes], frame)
        if index == len(self.Keyframes):
            # index is bigger than last frame, take last key
            return self.Keyframes[-1][1].duplicate()
        elif self.Keyframes[index][0] == frame:
            # index matches a keyframe
            return self.Keyframes[index][1].duplicate()
        else:
            if index == 0:
                # index is smaller than first frame, take first key
                return self.Keyframes[-1][1].duplicate()
            else:
                # index is in between two keyframes, interpolate
                before = self.Keyframes[index - 1]
                after = self.Keyframes[index]
                weight = (before[0] + frame) / after[0]
                return Pose(
                    glm.lerp(before[1].Position, after[1].Position, weight),
                    glm.lerp(before[1].Rotation, after[1].Rotation, weight),
                    glm.lerp(before[1].Scale, after[1].Scale, weight)
                )

    def insertKeyframePose(self, frame: int, pose: Pose) -> "Joint":
        """Inserts the given pose to the the keyframes.

        - If there is already a keyframe at the frame id, it will be overwritten.
        - If the frame number is negative, it counts as the n-th frame from the end.
        - This pose is added later to the rest pose to calculate the final animation."""
        if frame < 0: frame = max(0, self.getKeyframeRange(includeChildren=False)[1] + 1 - frame)
        index = bisect.bisect_left([key[0] for key in self.Keyframes], frame)

        if index == len(self.Keyframes) or self.Keyframes[index][0] != frame:
            bisect.insort(self.Keyframes, (frame, pose))
        else:
            self.Keyframes[index] = (frame, pose)

        return self

    def removeKeyframe(self, frame: int, recursive: bool = False) -> "Joint":
        """Removes the keyframe, if it exists, from the keyframe list.

        - If recursive is True -> Child joints do also load their rest pose.

        Returns itself."""
        index = bisect.bisect_left([key[0] for key in self.Keyframes], frame)

        if index != len(self.Keyframes) and self.Keyframes[index][0] == frame:
            self.Keyframes.pop(index)

        if recursive:
            for child in self.Children:
                child.removeKeyframe(frame=frame, recursive=True)

        return self

    def loadKeyframe(self, frame: int, recursive: bool = True) -> "Joint":
        """Sets the joint properties to the pose data of the keyframe.

        - This is not the final animation data. The animation is calculated as ``Pose = Restpose + Keyframe``
        - If recursive is True -> Child joints do also load their rest pose.

        Returns itself."""
        key = self.getKeyframePose(frame=frame)
        self.Position = key.Position
        self.Rotation = key.Rotation
        self.Scale = key.Scale

        if recursive:
            for child in self.Children:
                child.loadKeyframe(frame=frame, recursive=True)

        return self

    def writeKeyframe(self, frame: int, recursive: bool = True) -> "Joint":
        """Takes the current local joint properties, and sets them as Keyframe data.

        - If recursive is True -> Child joints do also load their rest pose.

        Returns itself."""
        self.insertKeyframePose(frame=frame, pose=Pose(
            position=self.Position,
            rotation=self.Rotation,
            scale=self.Scale
        ))

        if recursive:
            for child in self.Children:
                child.writeKeyframe(frame=frame, recursive=True)

        return self

    def loadRestPose(self, recursive: bool = True) -> "Joint":
        """Sets joint properties to the rest pose.

        - If recursive is True -> Child joints do also load their rest pose.

        Returns itself."""
        # self alignment
        self.Position = self.RestPose.Position
        self.Rotation = self.RestPose.Rotation
        self.Scale = self.RestPose.Scale

        # recursion
        if recursive:
            for child in self.Children:
                child.loadRestPose(recursive=True)

        return self

    def writeRestPose(self, recursive: bool = True, keep: list[str] = ['position', 'rotation', 'scale']) -> "Joint":
        """Sets the rest pose to the current joint properties.

        - If keep contains properties -> The Keyframes are modified to keep its spatial algiment in world space.
        - If keep is None or empty -> Keyframes do not change and thus the animation will change.
        - If recursive is True -> Child joints do also load their rest pose.

        Returns itself."""
        # remove change in rest pose from keyframes
        if keep:
            for frame, key in self.Keyframes:
                if 'position' in keep: key.Position = (self.SpaceInverse * self.RestPose.Space) * key.Position
                if 'rotation' in keep: key.Rotation = (self.RestPose.Rotation * glm.inverse(self.Rotation)) * key.Rotation
                if 'scale' in keep: key.Scale = (self.RestPose.Scale / self.Scale) * key.Scale

        # write rest pose
        self.RestPose.Position = self.Position
        self.RestPose.Rotation = self.Rotation
        self.RestPose.Scale = self.Scale

        # recursion
        if recursive:
            for child in self.Children:
                child.writeRestPose(recursive=True, keep=keep)

        return self

    def loadPose(self, frame: int, recursive: bool = True) -> "Joint":
        """Sets joint properties to the animation at the given frame id. The animation is defined as 'Pose = RestPose + Keyframe'.

        - If the frame number is negative, it will look for the n-th frame from the end.
        - If there are no keyframes, the joint propetries will not change.
        - If the frame id is out of the keyframe length, the nearest keyframe propetires are used.
        - If the frame id is between two keyframes, pose properties are linearly interpolated.
        - If recursive is True -> Child joints do also load their pose.

        Returns itself."""
        # get animation data
        key = self.getKeyframePose(frame)

        # calculate animation pose
        self._CurrentFrame = frame
        self.Position = self.RestPose.Space * key.Position
        self.Rotation = self.RestPose.Rotation * key.Rotation
        self.Scale = self.RestPose.Scale * key.Scale

        # may do it recursively
        if recursive:
            for child in self.Children:
                child.loadPose(frame, recursive=True)

        return self

    def writePose(self, frameId: int, recursive: bool = True) -> "Joint":
        """Sets joint properties as animation pose for the given frame id.

        - If there is already a keyframe at the frame id, it will be overwritten.
        - Inserts a new keyframe if there is none yet.
        - If the frame number is negative, it counts as the n-th frame from the end.
        - If recursive is True -> Child joints do also write their pose.

        Returns itself."""
        # calculate difference to rest pose
        newKey = Pose(
            position=self.RestPose.SpaceInverse * self.Position,
            rotation=glm.inverse(self.RestPose.Rotation) * self.Rotation,
            scale=self.Scale / self.RestPose.Scale
        )

        # add keyframe
        self.insertKeyframePose(frameId, pose=newKey)

        # recursion
        if recursive:
            for child in self.Children:
                child.writePose(frameId, recursive=True)

        return self

    def getKeyframeRange(self, includeChildren: bool = True) -> tuple[int, int]:
        """Returns the earliest and latest frame id of the animation.

        - If there are no keyframes, `(0, 0)` is returned.
        - If includeChildren is True -> The range considers the earliest and latest frames from its children too.

        The tuple layout is -> [FirstFrameId, LastFrameId]"""
        if len(self.Keyframes) == 0: return (0, 0)
        range = (self.Keyframes[0][0], self.Keyframes[-1][0])

        if includeChildren:
            for child in self.Children:
                childRange = child.getKeyframeRange(includeChildren=True)
                range = (min(range[0], childRange[0]), max(range[1], childRange[1]))

        return range

    def roll(self, degrees: float, recursive: bool = False) -> "Joint":
        """Rotates the joint along its local Y axis and updates the children so there is no spatial change.

        - RestPose and Keyframe data are not modified.

        Returns itself.
        """
        change = glm.angleAxis(glm.radians(degrees), (0, 1, 0))
        changeInverse = glm.inverse(change)

        self.Rotation = self.Rotation * change
        for child in self.Children:
            child.Position = changeInverse * child.Position
            child.Rotation = changeInverse * child.Rotation

            if recursive:
                child.roll(degrees, recursive=True)

        return self

    def attach(self, *nodes: "Joint", keep: list[str] = ['position', 'rotation', 'scale']) -> "Joint":
        return super().attach(*nodes, keep=keep)

    def detach(self, *nodes: "Joint", keep: list[str] = ['position', 'rotation', 'scale']) -> "Joint":
        return super().detach(*nodes, keep=keep)

    def clearParent(self, keep: list[str] = ['position', 'rotation', 'scale']) -> "Joint":
        return super().clearParent(keep=keep)

    def clearChildren(self, keep: list[str] = ['position', 'rotation', 'scale']) -> "Joint":
        return super().clearChildren(keep=keep)

    def applyPosition(self, position: glm.vec3 = None, recursive: bool = False, includeParentChange: list[Pose] = [], includeChildrenChange: list[Pose] = []) -> "Transform":
        return super().applyPosition(position, recursive, includeParentChange, includeChildrenChange)

    def applyRestposePosition(self, position: glm.vec3 = None, recursive: bool = False) -> "Joint":
        """"Resets the position of the Restpose to (0,0,0) or adds the given position.

        - This will load the restpose and overwrites the current pose of the transform!
        - You may want to call `loadPose` after this one or store the current properties.
        - Updates its keyframes position ONLY. Rotation and scale will be unchanged.
        - Updates its children Restposes positions to be spatially unchanged.
        - This does not update the childrens keyframes.

        Returns itself.
        """
        self.loadRestPose(recursive=False)
        for child in self.Children:
            child.loadRestPose(recursive=False)

        self.applyPosition(position=position, recursive=False)

        self.writeRestPose(recursive=False, keep=None)
        for child in self.Children:
            child.writeRestPose(recursive=False, keep=None)

        if recursive:
            for child in self.Children:
                child.applyRestposePosition(position, recursive=True)

        return self

    def applyRotation(self, rotation: glm.quat = None, recursive: bool = False, includeParentChange: list[Pose] = [], includeChildrenChange: list[Pose] = []) -> "Transform":
        return super().applyRotation(rotation, recursive, includeParentChange, includeChildrenChange)

    def applyRestposeRotation(self, rotation: glm.quat = None, recursive: bool = False) -> "Joint":
        """"Resets the rotation of the Restpose to (1,0,0,0) or adds the given rotation.

        - This will load the restpose and overwrites the current pose of the transform!
        - You may want to call `loadPose` after this one or store the current properties.
        - Updates its keyframes position ONLY. Rotation and scale will be unchanged.
        - Updates its children Restposes position and rotation to be spatially unchanged.
        - This does not update the childrens keyframes.

        Returns itself.
        """
        self.loadRestPose(recursive=False)
        for child in self.Children:
            child.loadRestPose(recursive=False)

        self.applyRotation(rotation=rotation, recursive=False)

        self.writeRestPose(recursive=False, keep=['position'])
        for child in self.Children:
            child.writeRestPose(recursive=False, keep=None)

        if recursive:
            for child in self.Children:
                child.applyRestposeRotation(rotation, recursive=True)

        return self

    def applyScale(self, scale: glm.vec3 = None, recursive: bool = False, includeParentChange: list[Pose] = [], includeChildrenChange: list[Pose] = []) -> "Transform":
        return super().appyScale(scale, recursive, includeParentChange, includeChildrenChange)

    def applyRestposeScale(self, scale: glm.vec3 = None, recursive: bool = False) -> "Joint":
        """"Resets the scale of the Restpose to (1,1,1) or adds the given scale.

        - This will load the restpose and overwrites the current pose of the transform!
        - You may want to call `loadPose` after this one or store the current properties.
        - Updates its keyframes position ONLY. Rotation and scale will be unchanged.
        - Updates its children Restposes position and scale to be spatially unchanged.
        - This does not update the childrens keyframes.

        Returns itself.
        """
        self.loadRestPose(recursive=False)
        for child in self.Children:
            child.loadRestPose(recursive=False)

        self.applyScale(scale=scale, recursive=False)

        self.writeRestPose(recursive=False, keep=['position'])
        for child in self.Children:
            child.writeRestPose(recursive=False, keep=None)

        if recursive:
            for child in self.Children:
                child.applyRestposeScale(scale, recursive=True)

        return self

    def setEuler(self, degrees: glm.vec3, order: str = 'ZXY', extrinsic: bool = True) -> "Joint":
        return super().setEuler(degrees, order, extrinsic)

    def filter(self, pattern: str, isEqual: bool = False, caseSensitive: bool = False) -> list["Joint"]:
        return super().filter(pattern, isEqual, caseSensitive)

    def filterRegex(self, pattern: str) -> list["Joint"]:
        return super().filterRegex(pattern)

    def layout(self, index: int = 0, depth: int = 0) -> list[tuple["Joint", int, int]]:
        return super().layout(index, depth)
