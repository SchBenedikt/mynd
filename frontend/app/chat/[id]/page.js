'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();

  useEffect(() => {
    if (params?.id) {
      router.replace(`/?chat=${params.id}`);
    }
  }, [params?.id, router]);

  return <div className="loading-chat">Lade Chat …</div>;
}
