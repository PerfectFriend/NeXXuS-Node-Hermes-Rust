import { useEffect, useRef } from 'react';
import QRCode from 'qrcode';

interface WalletQrCodeProps {
  address: string;
  size?: number;
}

export function WalletQrCode({ address, size = 180 }: WalletQrCodeProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvasRef.current && address) {
      QRCode.toCanvas(canvasRef.current, address, {
        width: size,
        margin: 2,
        color: { dark: '#e6edf3', light: '#0d1117' },
      });
    }
  }, [address, size]);

  if (!address || address === 'unsupported') {
    return <div style={{ width: size, height: size, background: '#161b22', borderRadius: 8 }} />;
  }

  return <canvas ref={canvasRef} width={size} height={size} style={{ borderRadius: 8 }} />;
}
