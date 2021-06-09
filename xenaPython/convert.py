from os.path import join, isfile, isdir
import os, sys
import datetime, json
import scanpy as sc

def dim_name(mapName, dim):
    return mapName + '_' + str(dim+1)

def buildsjson_scRNA_geneExp(output, cohort, label = None):
    fout = open(output +'.json', 'w')
    J = {}
    J['type'] ='genomicMatrix'
    J['dataSubtype'] = 'gene expression'
    if label:
        J['label'] = label
    else:
        J['label'] = os.path.basename(output)
    J["colNormalization"] = True
    J['cohort'] = cohort
    J['version'] = datetime.date.today().isoformat()
    json.dump(J, fout, indent = 4)
    fout.close()

def buildsjson_phenotype(output, cohort, label = None):
    fout = open(output +'.json', 'w')
    J = {}
    J['type'] ='clinicalMatrix'
    J['dataSubtype'] = 'phenotype'
    if label:
        J['label'] = label
    else:
        J['label'] = os.path.basename(output)
    J['cohort'] = cohort
    J['version'] = datetime.date.today().isoformat()
    json.dump(J, fout, indent = 4)
    fout.close()

def buildsjson_map (output, map_meta, cohort, label = None):
    fout = open(output +'.json', 'w')
    J = {}
    J['type'] ='clinicalMatrix'
    J['dataSubtype'] = 'maps'
    if label:
        J['label'] = label
    else:
        J['label'] = os.path.basename(output)
    J['cohort'] = cohort
    J['version'] = datetime.date.today().isoformat()

    J['map'] =[]
    for map_info in map_meta:
        J['map'].append({
            'label': map_info['label'],
            'dataSubType':  map_info['dataSubType'],
            'dimension': map_info['dimension']
            })

    json.dump(J, fout, indent = 4)
    fout.close()


def anndataMatrixToTsv(adata, matFname, transpose = True):
    """
    write adata expression matrix to .tsv file"
    """
    import pandas as pd
    import scipy.sparse

    mat = adata.X
    var = adata.var
    obs = adata.obs

    # Transposing matrix, has the samples on the rows: scanpy
    # Do not transpose, has the cells on the rows: starfish
    if (transpose):
        mat = mat.T
    if scipy.sparse.issparse(mat):
        mat = mat.tocsr() # makes writing to a file ten times faster, thanks Alex Wolf!

    ofh = open(matFname, "w")

    if (transpose):
        sampleNames = obs.index.tolist()
    else:
        sampleNames = var.index.tolist()
    ofh.write("gene\t")
    ofh.write("\t".join(sampleNames))
    ofh.write("\n")

    if (transpose):
        genes = var.index.tolist()
    else:
        genes = obs.genes.tolist()
    print("Writing %d genes in total" % len(genes))

    for i, geneName in enumerate(genes):
        if i % 2000==0:
            print("Wrote %d genes" % i)
        ofh.write(geneName)
        ofh.write("\t")
        if scipy.sparse.issparse(mat):
            row = mat.getrow(i).todense()
        else:
            row = mat[i,:]

        row.tofile(ofh, sep="\t", format="%.7g")
        ofh.write("\n")

    ofh.close()


def adataToXena(adata, path, studyName, transpose = True):
    """
    Given an anndata (adata) object, write dataset to a dataset directory under path.
    """

    if not isdir(path):
        os.makedirs(path)

    # build expression data file
    expfile = 'exprMatrix.tsv'
    matName = join(path, expfile)
    if isfile(matName):
        overwrite  = input("%s already exists. Overwriting existing files? Yes or No: " % matName)
        if overwrite.upper() == "YES":
            anndataMatrixToTsv(adata, matName, transpose)
    else:
        anndataMatrixToTsv(adata, matName, transpose)
    
    # build expression data .json file
    buildsjson_scRNA_geneExp(matName, studyName)

    # build meta data (phenotype data) file
    metafile = 'meta.tsv'
    metaName = join(path, metafile)
    if (transpose):
        adata.obs.to_csv(metaName, sep='\t')
    else:
        adata.var.to_csv(metaName, sep='\t')

    # build meta data .json file
    buildsjson_phenotype(metaName, studyName)

    # pca, tsne, umap, spatial coordinates
    if adata.obsm is not None:
        import numpy, pandas as pd

        dfs = []
        dfs_meta =[]
        for map in adata.obsm.keys():
            cols =[]
            if map == 'X_pca':
                mapName = "pca"
                dataSubType = 'embedding'
            elif map == 'X_umap':
                mapName = "umap"
                dataSubType = 'embedding'
            elif map == 'X_tsne':
                mapName = "tsne"
                dataSubType = 'embedding'
            elif map == 'X_spatial':
                mapName = 'spatial'
                dataSubType = 'spatial'

            row,col = adata.obsm[map].shape
            col = min(col, 3)

            for i in range (0, col):
                colName = dim_name(mapName, i)
                cols.append(colName)

            df = pd.DataFrame(adata.obsm[map][:,range(col)], columns=cols)
            df = df.set_index(adata.obs.index)
            dfs.append(df)
            dfs_meta.append({
                'label': mapName,
                'dataSubType': dataSubType,
                'dimension':cols
                })
        result = pd.concat(dfs, axis=1)

        map_file = 'maps.tsv'
        label = "maps"

        result.to_csv(join(path, map_file), sep='\t')
        buildsjson_map(join(path, map_file), dfs_meta, studyName, label)

def starfishExpressionMatrixToXena(mat, path, studyName):
    """
    Given a starfish ExpressionMatrix object (mat), write dataset to a dataset directory under path.
    """

    # build expression data file
    expfile = 'exprMatrix.tsv'
    matName = join(path, expfile)

    if isfile(matName):
        overwrite  = input("%s already exists. Overwriting existing files? Yes or No: " % matName)
        if overwrite.upper() == "YES":
            mat.to_pandas().transpose().to_csv(matName, sep='\t')
    else:
        mat.to_pandas().transpose().to_csv(matName, sep='\t')

    # build expression data .json file
    buildsjson_scRNA_geneExp(matName, studyName)

    # build meta data (phenotype data) file
    metafile = 'meta.tsv'
    metaName = join(path, metafile)

    cells = mat.cells.data.tolist()
    features = mat.cells.coords

    ofh = open(metaName, "w")
    ofh.write("\t")
    ofh.write("\t".join(features))
    ofh.write("\n")
    for i, cell in enumerate(cells):
        ofh.write(str(cell))
        for k in features:
            ofh.write("\t" + str(features[k].values[i]))
        ofh.write("\n")
    ofh.close()

    # build meta data .json file
    buildsjson_phenotype(metaName, studyName)


def scanpyLoomToXena(matrixFname, outputpath, studyName, transpose = True):
    """
    Given a scanpy loom file, write dataset to a dataset directory under path.
    Transposing matrix needed, as scanpy has the samples on the rows
    """
    loomToXena(matrixFname, outputpath, studyName, transpose)

def starfishLoomToXena(matrixFname, outputpath, studyName, transpose = False):
    """
    Given a starfish loom file, write dataset to a dataset directory under path.
    Transposing matrix not needed, as starfish has the cells on the rows
    """
    loomToXena(matrixFname, outputpath, studyName, transpose)

def loomToXena(matrixFname, outputpath, studyName, transpose = True):
    """
    Given a loom file, write dataset to a dataset directory under path.
    """
    adata = sc.read(matrixFname, first_column_names=True)
    adataToXena(adata, outputpath, studyName, transpose)

def h5adToXena(h5adFname, outputpath, studyName):
    """
    Given a h5ad file, write dataset to a dataset directory under path.
    """
    adata = sc.read(h5adFname, first_column_names=True)
    adataToXena(adata, outputpath, studyName)

def visiumToXena(visiumDataDir, outputpath, studyName):
    """
    Given a visium spaceranger output data directory, write dataset to a dataset directory under path.
    """
    # https://scanpy.readthedocs.io/en/stable/api/scanpy.read_visium.html

    for file in os.listdir(visiumDataDir):
        if file.endswith("filtered_feature_bc_matrix.h5"):
            count_file = file
            print (count_file)

    adata = sc.read_visium(visiumDataDir, count_file = count_file)
    sc.pp.normalize_total(adata, inplace=True)
    sc.pp.log1p(adata)
    adataToXena(adata, outputpath, studyName)


