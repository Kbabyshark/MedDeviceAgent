"""
/api/v1/admin/knowledge — 知识库管理接口（管理员）

/api/v1/knowledge — 知识检索接口（所有用户）
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File, Form

from app.core.deps import get_current_user_id, require_admin
from app.schemas.common import APIResponse, PaginatedData, PaginatedResponse
from app.services.knowledge_service import KnowledgeService
from app.rag.retriever import RagRetriever
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["knowledge"])
admin_router = APIRouter(tags=["admin-knowledge"])

_knowledge_service = KnowledgeService()
_retriever = RagRetriever()


# ================================================================
# 管理员接口
# ================================================================

@admin_router.post("/knowledge/upload")
async def upload_document(
    file: UploadFile = File(...),
    device_type: str = Form(..., description="设备型号"),
    doc_type: str = Form(..., description="文档类型: manual/faq/fault_code/policy"),
    version: str = Form(default="v1", description="版本号"),
    permission: str = Form(default="public", description="权限"),
    user_id: int = Depends(require_admin),
):
    """上传知识库文档（管理员）。

    支持 PDF / Word / Markdown / 纯文本。
    上传后自动触发后台 Chunk → Embedding → Qdrant 入库。
    """
    if doc_type not in ("manual", "faq", "fault_code", "policy"):
        raise HTTPException(status_code=400, detail="无效的文档类型")

    try:
        content = await file.read()
        result = await _knowledge_service.upload(
            content=content,
            filename=file.filename or "untitled",
            device_type=device_type,
            doc_type=doc_type,
            version=version,
            permission=permission,
            uploaded_by=str(user_id),
        )

        return APIResponse(
            message="文档上传成功，正在进行 Embedding 处理",
            data=result,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("upload_error", error=str(e), filename=file.filename)
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")


@admin_router.post("/knowledge/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    file: UploadFile = File(...),
    new_version: str = Form(..., description="新版本号"),
    user_id: int = Depends(require_admin),
):
    """更新文档版本并重新入库。"""
    try:
        content = await file.read()
        result = await _knowledge_service.update_version(
            doc_id=doc_id,
            content=content,
            filename=file.filename or "untitled",
            new_version=new_version,
            uploaded_by=str(user_id),
        )
        return APIResponse(message="版本更新成功，正在重新 Embedding", data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@admin_router.put("/knowledge/{doc_id}")
async def update_document(
    doc_id: str,
    body: dict = Body(...),
    user_id: int = Depends(require_admin),
):
    """编辑文档元数据（JSON body）。"""
    updated = await _knowledge_service.update_document(
        doc_id=doc_id,
        device_type=body.get("device_type", ""),
        doc_type=body.get("doc_type", ""),
        version=body.get("version", ""),
        permission=body.get("permission", ""),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="文档不存在")
    return APIResponse(message="文档已更新")


@admin_router.delete("/knowledge/{doc_id}")
async def delete_document(
    doc_id: str,
    user_id: int = Depends(require_admin),
):
    """删除知识库文档。"""
    deleted = await _knowledge_service.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
    return APIResponse(message="文档已标记删除")


@admin_router.get("/knowledge/{doc_id}/status")
async def get_document_status(
    doc_id: str,
    user_id: int = Depends(require_admin),
):
    """查看文档 Embedding 处理状态。"""
    status = await _knowledge_service.get_document_status(doc_id)
    if status is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return APIResponse(data=status)


@admin_router.get("/knowledge")
async def list_documents(
    device_type: str = Query(default="", description="按设备型号筛选"),
    doc_type: str = Query(default="", description="按文档类型筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int = Depends(require_admin),
):
    """列出知识库文档（管理员）。"""
    result = await _knowledge_service.list_documents(
        device_type=device_type,
        doc_type=doc_type,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=result["items"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        ),
    )


# ================================================================
# 用户接口
# ================================================================

@router.get("/devices")
async def list_device_types(
    user_id: int = Depends(get_current_user_id),
):
    """获取知识库中所有设备型号列表（用于聊天框下拉选择）。"""
    from app.services.knowledge_service import _conn as _ks_conn
    c = _ks_conn(); cur = c.cursor()
    cur.execute("SELECT DISTINCT device_type FROM knowledge_document WHERE device_type IS NOT NULL AND device_type != ''")
    rows = cur.fetchall(); c.close()
    return APIResponse(data=[r[0] for r in rows])


@router.post("/knowledge/search")
async def search_knowledge(
    query: str = Form(..., description="搜索查询"),
    device_type: str = Form(default="", description="设备型号"),
    doc_type: str = Form(default="", description="文档类型"),
    top_k: int = Form(default=5, ge=1, le=20, description="返回数量"),
    user_id: int = Depends(get_current_user_id),
):
    """知识检索测试接口。

    直接调用 RAG Retriever 搜索知识库并返回结果。
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")

    docs = await _retriever.retrieve(
        query=query.strip(),
        device_type=device_type,
        doc_type=doc_type,
        top_k=top_k,
    )

    return APIResponse(
        data={
            "query": query,
            "device_type": device_type,
            "doc_type": doc_type,
            "results": docs,
            "count": len(docs),
        },
    )
