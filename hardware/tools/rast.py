import fitz,sys
d=fitz.open(sys.argv[1]); pg=d[0]
clip=None
if len(sys.argv)>4:
    x0,y0,x1,y1=map(float,sys.argv[4].split(','))
    k=72/25.4; clip=fitz.Rect(x0*k,y0*k,x1*k,y1*k)
pix=pg.get_pixmap(dpi=int(sys.argv[3]),clip=clip); pix.save(sys.argv[2]); print(pix.width,pix.height)
