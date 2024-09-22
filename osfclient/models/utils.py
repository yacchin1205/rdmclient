from typing import AsyncGenerator, Optional, Union

from .core import OSFCore
from .file import File, Folder, ContainerMixin

from ..utils import norm_remote_path


def _is_path_matched(target_file_path: str, file_path: str):
    if target_file_path is None:
        return True
    file_path_segs = file_path.split('/')
    target_file_path_segs = target_file_path.split('/')
    if file_path_segs[-1] == '':
        file_path_segs = file_path_segs[:-1]
    if target_file_path_segs[-1] == '':
        target_file_path_segs = target_file_path_segs[:-1]
    for target_file_path_seg, file_path_seg in zip(target_file_path_segs,
                                                   file_path_segs):
        if target_file_path_seg.startswith('%') and \
           target_file_path_seg.endswith('%'):
            if target_file_path_seg[1:-1] not in file_path_seg:
                return False
        elif target_file_path_seg.startswith('%'):
            if not file_path_seg.endswith(target_file_path_seg[1:]):
                return False
        elif target_file_path_seg.endswith('%'):
            if not file_path_seg.startswith(target_file_path_seg[:-1]):
                return False
        else:
            if file_path_seg != target_file_path_seg:
                return False
    return True


def is_folder(file_or_folder: OSFCore):
    return hasattr(file_or_folder, 'files')


async def flatten(store: ContainerMixin) -> AsyncGenerator[Union[File, Folder], None]:
    async for file_ in store.children:
        yield file_
        if not is_folder(file_):
            continue
        async for child_file_ in flatten(file_):
            yield child_file_


async def find_ancestral_folder(store: ContainerMixin, target_file_path: str) -> Optional[ContainerMixin]:
    file_path_segs = target_file_path.split('/')
    if(len(file_path_segs) <= 1):
        return None
    folder = store
    path = ''
    i = 0
    is_found = False
    for i in range(len(file_path_segs) - 1):
        path += file_path_segs[i]
        is_found = False
        async for folder_ in folder.folders:
            if norm_remote_path(folder_.path) == path:
                folder = folder_
                is_found = True
                break
        if not is_found:
            break
        path += '/'
    return folder if i > 0 or is_found else None


async def find_by_path(store: ContainerMixin, target_file_path: str) -> Optional[Union[File, Folder]]:
    if target_file_path is None:
        return None
    file_path_segs = target_file_path.split('/')
    if(len(file_path_segs) == 1):
        async for file_ in store.children:
            if norm_remote_path(file_.path) == target_file_path:
                return file_
        return None
    parent_target_file_path = '/'.join(file_path_segs[:-1])
    parent_result = await find_by_path(store, parent_target_file_path)
    if parent_result is None:
        return None
    if not is_folder(parent_result):
        return None
    async for file_ in parent_result.children:
        if norm_remote_path(file_.path) == target_file_path:
            return file_
    return None


async def filter_by_path_pattern(store: ContainerMixin, target_file_path: str):
    async for file_ in _filter_by_path_pattern(store, target_file_path, 0):
        yield file_


async def _filter_by_path_pattern(store: ContainerMixin, target_file_path: str, depth: int):
    if target_file_path is None or target_file_path == '/':
        async for file_ in flatten(store):
            yield file_
        return
    file_path_segs = target_file_path.split('/')
    if file_path_segs[0] == '':
        file_path_segs = file_path_segs[1:]
    if file_path_segs[-1] == '':
        file_path_segs = file_path_segs[:-1]
    if(len(file_path_segs) == 1):
        async for file_ in store.children:
            if not _is_path_matched(target_file_path, file_.path):
                continue
            yield file_
            if not is_folder(file_):
                continue
            if depth > 0:
                continue
            async for child_ in flatten(file_):
                yield child_
        return
    parent_target_file_path = '/' + '/'.join(file_path_segs[:-1]) + '/'
    parent_result = _filter_by_path_pattern(store, parent_target_file_path, depth + 1)
    for rf_ in parent_result:
        if not is_folder(rf_):
            continue
        async for file_ in rf_.children:
            if not _is_path_matched(target_file_path, file_.path):
                continue
            yield file_
            if not is_folder(file_):
                continue
            if depth > 0:
                continue
            async for child_ in flatten(file_):
                yield child_
