import React from 'react';
import { Upload, Avatar, Button, message, Modal, Space, Spin } from 'antd';
import { UploadOutlined, CameraOutlined, DeleteOutlined } from '@ant-design/icons';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { RcFile, UploadProps } from 'antd/es/upload';
import { userAPI } from '@/services/api/user';

interface AvatarUploadProps {
  currentAvatarUrl?: string | null;
  size?: number;
  showUploadButton?: boolean;
  className?: string;
}

export const AvatarUpload: React.FC<AvatarUploadProps> = ({
  currentAvatarUrl,
  size = 96,
  showUploadButton = true,
  className = '',
}) => {
  const queryClient = useQueryClient();

  // 上传头像
  const uploadMutation = useMutation({
    mutationFn: (file: File) => userAPI.uploadAvatar(file),
    onSuccess: () => {
      void message.success('头像上传成功');
      // 更新用户资料缓存
      void queryClient.invalidateQueries({ queryKey: ['user-profile'] });
    },
    onError: (error: Error) => {
      void message.error(error.message || '头像上传失败');
    },
  });

  // 删除头像
  const deleteMutation = useMutation({
    mutationFn: () => userAPI.deleteAvatar(),
    onSuccess: () => {
      void message.success('头像已删除');
      void queryClient.invalidateQueries({ queryKey: ['user-profile'] });
    },
    onError: (error: Error) => {
      void message.error(error.message || '头像删除失败');
    },
  });

  const beforeUpload = (file: RcFile) => {
    // 验证文件类型
    const isJpgOrPng = file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/webp';
    if (!isJpgOrPng) {
      void message.error('只支持 JPG、PNG、WebP 格式的图片!');
      return false;
    }

    // 验证文件大小
    const isLt5M = file.size / 1024 / 1024 < 5;
    if (!isLt5M) {
      void message.error('图片大小不能超过 5MB!');
      return false;
    }

    return true;
  };

  const customRequest: UploadProps['customRequest'] = ({ file, onSuccess, onError }) => {
    void uploadMutation
      .mutateAsync(file as File)
      .then(() => {
        onSuccess?.('ok');
      })
      .catch((error: unknown) => {
        onError?.(error as Error);
      });
  };

  const handleDelete = () => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除当前头像吗？',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        void deleteMutation.mutateAsync();
      },
    });
  };

  return (
    <div className={`flex flex-col items-center space-y-4 ${className}`}>
      {/* 头像显示 */}
      <div className="relative">
        <Spin spinning={uploadMutation.isPending || deleteMutation.isPending}>
          <Upload
            name="avatar"
            listType="picture-circle"
            className="avatar-uploader"
            showUploadList={false}
            beforeUpload={beforeUpload}
            customRequest={customRequest}
            disabled={uploadMutation.isPending || deleteMutation.isPending}
          >
            {currentAvatarUrl ? (
              <Avatar
                size={size}
                src={currentAvatarUrl}
                className="cursor-pointer hover:opacity-80 transition-opacity"
              />
            ) : (
              <Avatar
                size={size}
                className="cursor-pointer hover:opacity-80 transition-opacity"
                style={{ backgroundColor: '#f56a00' }}
              >
                <CameraOutlined className="text-lg" />
              </Avatar>
            )}
          </Upload>
        </Spin>
      </div>

      {/* 操作按钮 */}
      {showUploadButton && (
        <Space direction="vertical" size="small" className="w-full">
          <Upload
            name="avatar"
            showUploadList={false}
            beforeUpload={beforeUpload}
            customRequest={customRequest}
            disabled={uploadMutation.isPending || deleteMutation.isPending}
          >
            <Button
              icon={<UploadOutlined />}
              loading={uploadMutation.isPending}
              className="w-full"
            >
              {currentAvatarUrl ? '更换头像' : '上传头像'}
            </Button>
          </Upload>

          {currentAvatarUrl && (
            <Button
              icon={<DeleteOutlined />}
              danger
              ghost
              loading={deleteMutation.isPending}
              onClick={handleDelete}
              className="w-full"
            >
              删除头像
            </Button>
          )}
        </Space>
      )}

      <style>{`
        .avatar-uploader .ant-upload {
          border: 2px dashed #d9d9d9;
          border-radius: 50%;
          transition: border-color 0.3s;
        }
        .avatar-uploader .ant-upload:hover {
          border-color: #1890ff;
        }
      `}</style>
    </div>
  );
};
