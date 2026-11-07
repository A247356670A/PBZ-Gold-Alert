using System;
using System.IO;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using System.Collections.Generic;
// Source is included for review. No custom compiled executable is shipped.
public static class PBZRelease {
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] public static extern bool SetDllDirectory(string path);
 [DllImport("oo2core_9_win64.dll", CallingConvention=CallingConvention.Cdecl)]
 static extern long OodleLZ_Decompress(byte[] input,long inputSize,[Out] byte[] output,long outputSize,int fuzz,int crc,int verbosity,IntPtr a,long b,IntPtr c,IntPtr d,IntPtr e,long f,int thread);
 static ulong Num(byte[] b,int p,int n,bool big) { ulong v=0;for(int j=0;j<n;j++)v|=(ulong)b[p+j]<<(8*(big?n-j-1:j));return v; }
 public static void CopyRange(Stream input,Stream target,long offset,long count) {
  if(offset<0 || count<0 || offset>input.Length-count)throw new InvalidDataException("Invalid payload range");
  input.Position=offset;byte[] buffer=new byte[1048576];
  while(count>0){int n=input.Read(buffer,0,(int)Math.Min(count,buffer.Length));if(n==0)throw new EndOfStreamException();target.Write(buffer,0,n);count-=n;}
 }
 public static void AppendBase(string paks,string cid,string key,Stream target,long expectedBytes) {
  byte[] toc=File.ReadAllBytes(Path.Combine(paks,"ProjectPBZ-Windows.utoc"));
  int count=(int)Num(toc,24,4,false),blockSize=(int)Num(toc,44,4,false),found=-1;
  byte[] id=new byte[12];for(int j=0;j<12;j++)id[j]=Convert.ToByte(cid.Substring(j*2,2),16);
  for(int i=0;i<count;i++){bool same=true;for(int j=0;j<12;j++)if(toc[144+i*12+j]!=id[j]){same=false;break;}if(same){found=i;break;}}
  if(found<0)throw new Exception("Required original audio chunk not found");
  int entry=144+count*12+found*10;long offset=(long)Num(toc,entry,5,true),size=(long)Num(toc,entry+5,5,true);
  if(size!=expectedBytes)throw new InvalidDataException("Original audio chunk size mismatch");
  long partitionSize=(long)Num(toc,88,8,false);
  int blocks=144+count*22+(int)Num(toc,84,4,false)*4+(int)Num(toc,96,4,false)*4;
  byte[] aeskey=new byte[key.Length/2];for(int i=0;i<aeskey.Length;i++)aeskey[i]=Convert.ToByte(key.Substring(i*2,2),16);
  var inputs=new Dictionary<long,FileStream>();
  try {using(Aes aes=Aes.Create()){
   aes.Key=aeskey;aes.Mode=CipherMode.ECB;aes.Padding=PaddingMode.None;
   using(ICryptoTransform decrypt=aes.CreateDecryptor()) {
    for(long bi=offset/blockSize;bi<(offset+size+blockSize-1)/blockSize;bi++){
     int at=blocks+checked((int)bi)*12;long disk=(long)Num(toc,at,5,false);
     int cs=(int)Num(toc,at+5,3,false),us=(int)Num(toc,at+8,3,false),method=toc[at+11];
     long partition=disk/partitionSize,position=disk%partitionSize;
     FileStream input;
     if(!inputs.TryGetValue(partition,out input)){
      input=File.OpenRead(Path.Combine(paks,"ProjectPBZ-Windows"+(partition==0?"":"_s"+partition)+".ucas"));inputs.Add(partition,input);
     }
     input.Position=position;byte[] encrypted=new byte[(cs+15)&~15];int read=0;
     while(read<encrypted.Length){int got=input.Read(encrypted,read,encrypted.Length-read);if(got==0)throw new EndOfStreamException();read+=got;}
     byte[] compressed=new byte[encrypted.Length];decrypt.TransformBlock(encrypted,0,encrypted.Length,compressed,0);
     byte[] output;
     if(method==0){output=compressed;if(cs!=us)throw new Exception("Invalid stored block");}
     else if(method==1){output=new byte[us];long got=OodleLZ_Decompress(compressed,cs,output,us,1,0,0,IntPtr.Zero,0,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,0,3);if(got!=us)throw new Exception("Audio decompression failed");}
     else throw new Exception("Unsupported compression method");
     long start=Math.Max(offset,bi*blockSize),end=Math.Min(offset+size,bi*blockSize+us);
     if(end>start)target.Write(output,(int)(start-bi*blockSize),(int)(end-start));
    }
   }
  }} finally {foreach(FileStream input in inputs.Values)input.Dispose();}
 }
}
